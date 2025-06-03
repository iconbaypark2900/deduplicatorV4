# backend/services/pipeline_orchestrator.py
import logging
import os
import uuid
import pickle # For LSH index
from typing import Dict, Optional, List

from ingestion.pdf_reader import extract_text_from_pdf, extract_pages_from_pdf
from ingestion.preprocessing import measure_medical_confidence
from similarity.hashing import (
    compute_document_hash, 
    get_minhash, 
    create_lsh_index, 
    query_lsh_index,
    get_lsh_index_instance
)
from similarity.engine import SimilarityEngine 
from similarity.tfidf import (
    insert_document_vector as store_tfidf_vector_in_db, 
    tfidf_search as search_tfidf_vectors_in_db,
    load_fitted_tfidf_vectorizer 
)
from utils.page_tracker import update_page_hash_map
from backend.services.logger import log_upload 
from utils.config import settings # For LSH_THRESHOLD, DOC_SIMILARITY_THRESHOLD

# Database imports
from utils.database import get_db, upsert_document_metadata, get_document_by_hash

# Import Celery tasks
# from backend.tasks.clustering_tasks import run_clustering_task # No longer called directly here

logger = logging.getLogger(__name__)

# --- LSH Index Management --- MOVED TO similarity/hashing.py
# LSH_INDEX_FILE = "storage/metadata/lsh_index.pkl"
# LSH_THRESHOLD = settings.LSH_JACCARD_THRESHOLD if hasattr(settings, 'LSH_JACCARD_THRESHOLD') else 0.8 
# LSH_NUM_PERM = settings.LSH_NUM_PERMUTATIONS if hasattr(settings, 'LSH_NUM_PERMUTATIONS') else 128

# Ensure metadata directory exists for LSH index - MOVED
# os.makedirs(os.path.dirname(LSH_INDEX_FILE), exist_ok=True)

# get_lsh_index_instance and save_lsh_index_instance MOVED to similarity/hashing.py
# def get_lsh_index_instance(): ... 
# def save_lsh_index_instance(lsh_index): ...

class PipelineOrchestrator:
    def __init__(self):
        self.similarity_engine = SimilarityEngine()
        if load_fitted_tfidf_vectorizer() is None:
             logger.warning("TF-IDF Vectorizer is not loaded or not fitted via similarity.tfidf._load_vectorizer(). "
                          "Ensure it's initialized (e.g., via fit_vectorizer_and_save during app startup).")

    # This method is called by the Celery task defined in backend.tasks.pipeline_tasks.py
    def process_document(self, pdf_path: str, original_filename: str, doc_id: Optional[str] = None, task_self=None) -> Dict:
        if not doc_id:
            doc_id = str(uuid.uuid4())

        processing_status = {"doc_id": doc_id, "filename": original_filename, "stages": {}, "final_status": "processing_started"}
        
        # Celery progress update example (if task_self is passed)
        if task_self:
            task_self.update_state(state='PROGRESS', meta={'current_stage': 'InitialSetup', 'progress': 1, 'doc_id': doc_id})

        try:
            with get_db() as db:
                # Initial metadata entry
                upsert_document_metadata(db, doc_id, filename=original_filename, status="processing_extraction")

            # --- Stage 0: Text Extraction & Initial Page Processing ---
            logger.info(f"[{doc_id}] Stage 0: Extracting text for {original_filename}")
            full_text = extract_text_from_pdf(pdf_path)
            if not full_text:
                logger.warning(f"[{doc_id}] No text extracted from {original_filename}.")
                with get_db() as db:
                    upsert_document_metadata(db, doc_id, status="error_text_extraction")
                log_upload(doc_id, original_filename, "error_text_extraction")
                processing_status["stages"]["text_extraction"] = "Failed: No text"
                processing_status["final_status"] = "error_text_extraction"
                return {"status": "error", "message": "Text extraction failed", **processing_status}

            page_texts = extract_pages_from_pdf(pdf_path)
            medical_confidences = [measure_medical_confidence(pt) for pt in page_texts if pt]
            # Using doc_id for page_tracker, assuming it's the central ID
            update_page_hash_map( 
                doc_id=doc_id, filename=original_filename, page_texts=page_texts,
                medical_confidences=medical_confidences, image_paths=[None]*len(page_texts)
            )
            processing_status["stages"]["text_extraction"] = "Completed"
            with get_db() as db:
                upsert_document_metadata(db, doc_id, status="processing_hash_check", page_count=len(page_texts))


            # --- Stage 1: Exact Duplicate Check (Hash Check) ---
            logger.info(f"[{doc_id}] Stage 1: Performing exact hash check.")
            # Assuming pdf_path is a temporary path to the file content for hashing
            doc_hash = compute_document_hash(pdf_path) 
            
            if not doc_hash:
                logger.warning(f"[{doc_id}] Could not compute content hash for {original_filename}.")
                with get_db() as db:
                    upsert_document_metadata(db, doc_id, status="error_hash_computation")
                log_upload(doc_id, original_filename, "error_hash_computation")
                processing_status["stages"]["exact_hash_check"] = "Failed: Hash computation error"
                processing_status["final_status"] = "error_hash_computation"
                return {"status": "error", "message": "Hash computation failed", **processing_status}

            with get_db() as db:
                existing_doc_meta = get_document_by_hash(db, doc_hash)
                if existing_doc_meta and existing_doc_meta.doc_id != doc_id:
                    logger.info(f"[{doc_id}] Exact duplicate of {existing_doc_meta.doc_id} found by hash {doc_hash[:10]}.")
                    upsert_document_metadata(db, doc_id, status="exact_duplicate", matched_doc_id=existing_doc_meta.doc_id, content_hash=doc_hash)
                    log_upload(doc_id, original_filename, "exact_duplicate")
                    processing_status["stages"]["exact_hash_check"] = f"Exact duplicate of {existing_doc_meta.doc_id}"
                    processing_status["final_status"] = "exact_duplicate"
                    return {"status": "exact_duplicate", "matched_doc_id": existing_doc_meta.doc_id, **processing_status}
                else:
                    # No exact duplicate, or it's the same document being reprocessed. Store hash for current doc.
                    upsert_document_metadata(db, doc_id, content_hash=doc_hash, status="processing_lsh")
            processing_status["stages"]["exact_hash_check"] = "No exact match found or hash updated."


            # --- Stage 2: Near Duplicate Check (MinHash LSH) ---
            logger.info(f"[{doc_id}] Stage 2: Performing MinHash LSH check.")
            # Use LSH_NUM_PERM from hashing.py (via settings) or define it if needed from settings directly
            minhash_obj = get_minhash(full_text) # NUM_PERM is now default in get_minhash from settings
            
            # Load the LSH index on demand to get the latest version
            current_lsh_index = get_lsh_index_instance() # This now comes from similarity.hashing
            potential_duplicates_ids = query_lsh_index(current_lsh_index, minhash_obj)
            potential_duplicates_ids = [pid for pid in potential_duplicates_ids if pid != doc_id] # Filter self

            minhash_signature_hex = ''.join(format(x, '02x') for x in minhash_obj.hashvalues.tobytes())


            if potential_duplicates_ids:
                logger.info(f"[{doc_id}] Potential LSH matches: {potential_duplicates_ids}.")
                processing_status["stages"]["minhash_lsh_check"] = f"Potential LSH matches found: {len(potential_duplicates_ids)}"
            else:
                processing_status["stages"]["minhash_lsh_check"] = "No LSH matches"
            
            with get_db() as db: # Store MinHash signature
                upsert_document_metadata(db, doc_id, minhash_signature=minhash_signature_hex, status="processing_tfidf")
            
            # The LSH_INDEX is now considered read-only in this context.
            # It's updated by a separate, periodic Celery task.
            # We no longer add to it or save it here to avoid concurrency issues.
            # MinHash signature is saved to DB, LSH index rebuild task will pick it up.


            # --- Stage 3: Content Similarity (TF-IDF) & Vector Storage ---
            logger.info(f"[{doc_id}] Stage 3: TF-IDF vectorization and similarity check.")
            tfidf_vector = self.similarity_engine.vectorize(full_text)

            if tfidf_vector is not None:
                with get_db() as db:
                   store_tfidf_vector_in_db(db, doc_id, tfidf_vector) # vector_type='tfidf' is default
                logger.info(f"[{doc_id}] TF-IDF vector computed and stored in DB.")
                processing_status["stages"]["tfidf_vectorization"] = "Completed"

                with get_db() as db:
                   best_match_info = search_tfidf_vectors_in_db(db, tfidf_vector, threshold=settings.DOC_SIMILARITY_THRESHOLD)
                
                if best_match_info and best_match_info.get("matched_doc") != doc_id : # Ensure not matching self
                    matched_doc_id = best_match_info['matched_doc']
                    similarity = best_match_info['similarity']
                    logger.info(f"[{doc_id}] TF-IDF duplicate found: {matched_doc_id} with similarity {similarity:.4f}")
                    processing_status["stages"]["tfidf_similarity_check"] = f"Content duplicate of {matched_doc_id}"
                    processing_status["final_status"] = "content_duplicate"
                    with get_db() as db:
                        upsert_document_metadata(db, doc_id, status="content_duplicate", matched_doc_id=matched_doc_id, similarity_score=similarity)
                    log_upload(doc_id, original_filename, "content_duplicate")
                else:
                    logger.info(f"[{doc_id}] No significant TF-IDF similarity found.")
                    processing_status["stages"]["tfidf_similarity_check"] = "Unique by content"
                    processing_status["final_status"] = "unique"
                    with get_db() as db:
                        upsert_document_metadata(db, doc_id, status="unique")
                    log_upload(doc_id, original_filename, "unique")
            else:
                logger.warning(f"[{doc_id}] TF-IDF vector could not be generated for {original_filename}.")
                processing_status["stages"]["tfidf_vectorization"] = "Failed"
                processing_status["final_status"] = "error_tfidf_vectorization"
                with get_db() as db:
                   upsert_document_metadata(db, doc_id, status="error_tfidf_vectorization")
                log_upload(doc_id, original_filename, "error_tfidf_vectorization")

            # --- Stage 4: Trigger DBSCAN Clustering Update (Placeholder) ---
            # Clustering is now handled by a separate, periodic Celery Beat task
            # and is no longer triggered after each individual document processing.
            # if processing_status["final_status"] not in ["exact_duplicate", "error_text_extraction", "error_tfidf_vectorization", "error_hash_computation"]:
            #     logger.info(f"[{doc_id}] Stage 4: DBSCAN clustering update is now periodic, not triggered here.")
            #     # run_clustering_task.delay() # REMOVED
            #     processing_status["stages"]["dbscan_trigger"] = "Handled by periodic task"
            #     if task_self:
            #         task_self.update_state(state='PROGRESS', meta={'current_stage': 'DBSCAN Trigger Skipped (Periodic)', 'progress': 95, 'doc_id': doc_id})

            logger.info(f"[{doc_id}] Pipeline processing completed for {original_filename} with status: {processing_status['final_status']}")
            # Final state update is handled by the calling Celery task in pipeline_tasks.py
            return {"status": processing_status["final_status"], **processing_status}

        except Exception as e:
            logger.error(f"[{doc_id}] Critical error in pipeline for {original_filename}: {e}", exc_info=True)
            processing_status["stages"]["critical_error"] = str(e)
            processing_status["final_status"] = "error_pipeline_critical"
            try:
                with get_db() as db:
                    upsert_document_metadata(db, doc_id, status="error_pipeline_critical", filename=original_filename) # Ensure filename is set on error
            except Exception as db_err:
                logger.error(f"[{doc_id}] Failed to log critical error to DB: {db_err}")
            log_upload(doc_id, original_filename, "error_pipeline_critical")
            # Celery task failure is handled by the calling Celery task in pipeline_tasks.py
            return {"status": "error", "message": str(e), **processing_status}
        finally:
            # pdf_path is usually a temporary path created by the caller (e.g., API endpoint)
            # The caller should be responsible for cleaning it up.
            # If the orchestrator itself creates a copy, then it should clean it.
            logger.debug(f"[{doc_id}] Orchestrator finished processing for {pdf_path}")
            pass

# Example of how this might be used if not a Celery task directly:
# if __name__ == '__main__':
#     # This would require a dummy settings.py and utils/database.py setup for standalone run
#     # Configure logging for standalone test
#     logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
#     
#     # Create a dummy PDF file for testing
#     dummy_pdf_path = "storage/tmp/dummy_test.pdf"
#     if not os.path.exists(os.path.dirname(dummy_pdf_path)):
#         os.makedirs(os.path.dirname(dummy_pdf_path))
#     try:
#         from pypdf import PdfWriter
#         writer = PdfWriter()
#         writer.add_blank_page(width=612, height=792) # Standard US Letter
#         # You might need to add actual text content to the PDF for meaningful processing
#         # For now, it will be a blank PDF. Most stages will log warnings or pass through.
#         with open(dummy_pdf_path, "wb") as f_dummy:
#             writer.write(f_dummy)
#         logger.info(f"Created dummy PDF for testing: {dummy_pdf_path}")
#
#         # Create tables if they don't exist (requires DB connection)
#         # from utils.database import create_all_tables
#         # create_all_tables() # Make sure your DATABASE_URL is set in .env or config
#
#         orchestrator = PipelineOrchestrator()
#         result = orchestrator.process_document(pdf_path=dummy_pdf_path, original_filename="dummy_test.pdf")
#         logger.info(f"Orchestrator result: {result}")
#
#     except ImportError as ie:
#         logger.error(f"Import error during standalone test, ensure all dependencies are available: {ie}")
#     except Exception as ex:
#         logger.error(f"Error during standalone test: {ex}", exc_info=True)
#     finally:
#         if os.path.exists(dummy_pdf_path):
#             os.remove(dummy_pdf_path) 