import logging
from sqlalchemy.orm import joinedload

from ..celery_app import app
from utils.database import get_db, DocumentMetadata, Page
from similarity.tfidf import fit_vectorizer_and_save, tfidf_vectorize, insert_document_vector, VECTORIZER_FILE
import os

logger = logging.getLogger(__name__)

@app.task(name="tasks.manage_tfidf_vectorizer")
def manage_tfidf_vectorizer_task(force_refit: bool = False):
    """
    Manages the TF-IDF vectorizer.
    Fits a new vectorizer if one doesn't exist or if force_refit is True.
    After fitting, it re-calculates and updates TF-IDF vectors for all documents.
    """
    logger.info("Starting TF-IDF vectorizer management task...")

    if not force_refit and os.path.exists(VECTORIZER_FILE):
        # Basic check: Does the file exist? A more robust check might try to load it
        # and see if it's usable/fitted, but fit_vectorizer_and_save will overwrite it anyway.
        logger.info(f"TF-IDF vectorizer file already exists at {VECTORIZER_FILE} and force_refit is False. Skipping fitting.")
        # Even if we skip fitting, we might want to ensure all docs have vectors.
        # For now, this task focuses on the fitting and subsequent universal update.
        # A separate task could handle vectorizing missing ones with the current vectorizer.
        # However, if the goal is a full refit and update, this is the main path.
        # If we want to ensure all documents *always* have a vector with the *current* vectorizer,
        # that might be a different periodic check or part of the document processing pipeline itself.
        # For now, let's assume if we're not refitting, this task's main job is done.
        # A more advanced version could verify all documents have vectors with the *current* vectorizer.
        # logger.info("TF-IDF vectorizer management task finished (skipped fitting).")
        # return


    logger.info("Proceeding to fit/refit TF-IDF vectorizer.")
    
    all_doc_texts = []
    doc_ids_for_revectorization = []

    try:
        with get_db() as db:
            # Fetch all documents and their pages to reconstruct text
            # Using joinedload to eagerly load pages to reduce individual queries per document
            logger.info("Fetching document texts for TF-IDF vectorizer fitting...")
            documents = db.query(DocumentMetadata).options(joinedload(DocumentMetadata.pages.and_(Page.text_snippet != None))).all()
            
            if not documents:
                logger.warning("No documents found in the database to fit the TF-IDF vectorizer. Aborting task.")
                return

            for doc in documents:
                # Ensure pages are sorted by page_number if not guaranteed by query
                sorted_pages = sorted(doc.pages, key=lambda p: p.page_number)
                full_text = "\\n".join(p.text_snippet for p in sorted_pages if p.text_snippet)
                if full_text.strip():
                    all_doc_texts.append(full_text)
                    doc_ids_for_revectorization.append(doc.doc_id) # Keep track of doc_ids and their corresponding texts
                else:
                    logger.warning(f"Document {doc.doc_id} has no text content after page concatenation. Skipping for fitting.")
            
            if not all_doc_texts:
                logger.warning("No text content found in any documents. Cannot fit TF-IDF vectorizer. Aborting task.")
                return

            logger.info(f"Fitting TF-IDF vectorizer on {len(all_doc_texts)} documents.")
            # This function saves the vectorizer to VECTORIZER_FILE
            new_vectorizer = fit_vectorizer_and_save(all_doc_texts)
            
            if new_vectorizer is None or not hasattr(new_vectorizer, 'vocabulary_') or not new_vectorizer.vocabulary_:
                logger.error("Failed to fit or save a valid TF-IDF vectorizer. Aborting re-vectorization.")
                return

            logger.info("TF-IDF vectorizer fitted and saved. Now re-calculating and updating all document vectors.")
            
            # Re-vectorize all documents that had text
            # This assumes fit_vectorizer_and_save has updated the global VECTORIZER
            # or that tfidf_vectorize will load the newly saved one.
            for i, doc_id in enumerate(doc_ids_for_revectorization):
                doc_text = all_doc_texts[i] # Get the corresponding text
                logger.debug(f"Re-vectorizing document {doc_id} ({i+1}/{len(doc_ids_for_revectorization)})")
                vector = tfidf_vectorize(doc_text) # Uses the newly fitted vectorizer
                if vector is not None:
                    try:
                        insert_document_vector(db, doc_id, vector, vector_type='tfidf')
                        # db.commit() might be too frequent here if insert_document_vector doesn't commit
                        # insert_document_vector in similarity/tfidf.py does its own commit.
                    except Exception as e_insert:
                        logger.error(f"Error updating vector for document {doc_id} in DB: {e_insert}", exc_info=True)
                        # Potentially rollback session or handle error, for now just log
                else:
                    logger.warning(f"Failed to generate TF-IDF vector for document {doc_id} after refitting. Skipping DB update for this doc.")
            
            # db.commit() # Final commit if insert_document_vector doesn't do it.
            logger.info("Successfully re-calculated and updated TF-IDF vectors for all relevant documents.")

    except Exception as e:
        logger.error(f"Critical error in TF-IDF vectorizer management task: {e}", exc_info=True)
        # Depending on alerting, might want to raise or notify

    logger.info("TF-IDF vectorizer management task finished.") 