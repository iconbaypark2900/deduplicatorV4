# backend/services/pipeline_orchestrator.py
import logging
import os
import uuid # For generating document IDs if not provided

from ingestion.pdf_reader import extract_text_from_pdf, extract_pages_from_pdf
from ingestion.preprocessing import measure_medical_confidence # For page metadata
from similarity.hashing import compute_document_hash, get_minhash # For exact and MinHash
# You'll need a way to access/query your LSH index (from similarity.hashing or a dedicated service)
# from similarity.hashing import LSH_INDEX_SINGLETON # Placeholder
from similarity.engine import SimilarityEngine # For TF-IDF vectorization
from similarity.tfidf import (
    tfidf_search,
    insert_document_vector,
)
from utils.database import get_db, get_document_by_hash
from utils.config import settings
from utils.page_tracker import update_page_hash_map
from backend.services.logger import log_system_event, log_upload # For logging
# from backend.services.clustering_service import trigger_dbscan_update # Placeholder
# from celery_app import app # Assuming your Celery app instance is defined

logger = logging.getLogger(__name__)

# Placeholder for LSH index - this needs proper management (persistence, updates)
# LSH_INDEX = LSH_INDEX_SINGLETON() # This would come from similarity.hashing or a service

class PipelineOrchestrator:
    def __init__(self):
        self.similarity_engine = SimilarityEngine() # This is now TF-IDF specific
        # Initialize database connections or other services if needed

    # This method would likely be a Celery task
    # @app.task(bind=True)
    # def process_document_task(self, task_self, pdf_path: str, original_filename: str, doc_id: Optional[str] = None):
    def process_document(self, pdf_path: str, original_filename: str, doc_id: Optional[str] = None) -> Dict:
        """
        Processes a single PDF document through the deduplication pipeline.
        This method would be wrapped by or called from a Celery task.
        """
        if not doc_id:
            doc_id = str(uuid.uuid4())

        processing_status = {"doc_id": doc_id, "filename": original_filename, "stages": {}}
        current_task_state = {} # For Celery progress

        try:
            # --- Stage 0: Text Extraction & Initial Page Processing ---
            logger.info(f"[{doc_id}] Stage 0: Extracting text and pages for {original_filename}")
            # current_task_state = {'stage': 'Text Extraction', 'progress': 10}
            # task_self.update_state(state='PROGRESS', meta=current_task_state)

            full_text = extract_text_from_pdf(pdf_path)
            if not full_text:
                logger.warning(f"[{doc_id}] No text extracted from {original_filename}. Aborting.")
                processing_status["stages"]["text_extraction"] = "Failed: No text"
                # log_upload(doc_id, original_filename, "extraction_failed")
                return {"status": "error", "message": "Text extraction failed", **processing_status}

            page_texts = extract_pages_from_pdf(pdf_path)
            medical_confidences = [measure_medical_confidence(pt) for pt in page_texts]

            # For now, image_paths might be None or placeholders if not generated here
            image_paths = [None] * len(page_texts) 

            update_page_hash_map(
                doc_id=doc_id,
                filename=original_filename,
                page_texts=page_texts,
                medical_confidences=medical_confidences,
                # duplicate_confidences will be updated later if TF-IDF page similarities are computed
                image_paths=image_paths
            )
            processing_status["stages"]["text_extraction"] = "Completed"
            # current_task_state['progress'] = 20
            # task_self.update_state(state='PROGRESS', meta=current_task_state)

            # --- Stage 1: Exact Duplicate Check (Hash Check) ---
            logger.info(f"[{doc_id}] Stage 1: Performing exact hash check.")
            doc_hash = compute_document_hash(pdf_path)  # Uses the same extracted text implicitly

            existing_doc = None
            try:
                with get_db() as db:
                    existing_doc = get_document_by_hash(db, doc_hash)
            except Exception as db_err:
                logger.error(f"[{doc_id}] Error querying for existing hash: {db_err}")

            if existing_doc and existing_doc.doc_id != doc_id:
                logger.info(
                    f"[{doc_id}] Exact duplicate found: {existing_doc.doc_id}. Marking as duplicate."
                )
                processing_status["stages"]["exact_hash_check"] = f"Duplicate of {existing_doc.doc_id}"
                return {"status": "exact_duplicate", "matched_doc_id": existing_doc.doc_id, **processing_status}

            processing_status["stages"]["exact_hash_check"] = "No exact match"
            # current_task_state['progress'] = 30
            # task_self.update_state(state='PROGRESS', meta=current_task_state)


            # --- Stage 2: Near Duplicate Check (MinHash LSH) ---
            logger.info(f"[{doc_id}] Stage 2: Performing MinHash LSH check.")
            minhash = get_minhash(full_text)
            # potential_duplicates = LSH_INDEX.query(minhash) # Query your LSH index
            # if potential_duplicates:
            #     logger.info(f"[{doc_id}] Found {len(potential_duplicates)} potential LSH matches: {potential_duplicates}")
            #     # Further verification might be needed here, or pass to TF-IDF
            #     processing_status["stages"]["minhash_lsh_check"] = f"Potential matches: {potential_duplicates}"
            # else:
            #     processing_status["stages"]["minhash_lsh_check"] = "No LSH matches"
            processing_status["stages"]["minhash_lsh_check"] = "Completed (placeholder logic)"
            # current_task_state['progress'] = 50
            # task_self.update_state(state='PROGRESS', meta=current_task_state)

            # --- Stage 3: Content Similarity (TF-IDF) & Vector Storage ---
            logger.info(f"[{doc_id}] Stage 3: Computing TF-IDF vector and checking similarity.")
            tfidf_vector = self.similarity_engine.vectorize(full_text)

            if tfidf_vector is not None:
                try:
                    with get_db() as db:
                        insert_document_vector(db, doc_id, tfidf_vector)
                    logger.info(f"[{doc_id}] TF-IDF vector stored in DB.")
                    processing_status["stages"]["tfidf_vectorization"] = "Completed"
                except Exception as vec_err:
                    logger.error(f"[{doc_id}] Failed to store TF-IDF vector: {vec_err}")
                    processing_status["stages"]["tfidf_vectorization"] = "Error storing vector"
                
                best_match_info = tfidf_search(tfidf_vector, threshold=settings.DOC_SIMILARITY_THRESHOLD)
                if best_match_info and best_match_info.get("matched_doc") != doc_id:
                    matched_doc = best_match_info["matched_doc"]
                    sim_val = best_match_info["similarity"]
                    processing_status["stages"]["tfidf_similarity_check"] = f"Duplicate of {matched_doc}"
                    processing_status["matched_doc"] = matched_doc
                    processing_status["similarity"] = sim_val
                else:
                    processing_status["stages"]["tfidf_similarity_check"] = "No similar document"
            else:
                processing_status["stages"]["tfidf_vectorization"] = "Vectorization failed"
                processing_status["stages"]["tfidf_similarity_check"] = "Skipped"
            # current_task_state['progress'] = 80
            # task_self.update_state(state='PROGRESS', meta=current_task_state)

            # --- Stage 4: Trigger DBSCAN Clustering Update ---
            # This is often done periodically or after a batch of new documents.
            # For real-time (or near real-time), you might enqueue another Celery task.
            logger.info(f"[{doc_id}] Stage 4: Triggering DBSCAN clustering update (asynchronously).")
            # trigger_dbscan_update.delay() # Placeholder for Celery task
            processing_status["stages"]["dbscan_trigger"] = "Triggered"
            # current_task_state['progress'] = 100
            # task_self.update_state(state='SUCCESS', meta=current_task_state)

            logger.info(f"[{doc_id}] Pipeline processing completed for {original_filename}.")
            return {"status": "success", **processing_status}

        except Exception as e:
            logger.error(f"[{doc_id}] Error in pipeline for {original_filename}: {e}", exc_info=True)
            # current_task_state['error'] = str(e)
            # task_self.update_state(state='FAILURE', meta=current_task_state)
            # log_upload(doc_id, original_filename, "pipeline_error")
            # update_document_status_in_db(doc_id, "error") # Placeholder
            processing_status["stages"]["error"] = str(e)
            return {"status": "error", "message": str(e), **processing_status}
        finally:
            # Clean up the temporary PDF file if it was saved by the caller
            # Or, if the orchestrator saves it, clean up here.
            # if os.path.exists(pdf_path):
            #     os.remove(pdf_path) # Be careful if pdf_path is the original uploaded file location
            pass