# backend/tasks/pipeline_tasks.py
import logging
import os
from backend.celery_app import app
from backend.services.pipeline_orchestrator import PipelineOrchestrator
from utils.config import settings # For any task-specific configurations if needed

logger = logging.getLogger(__name__)

# Ensure necessary storage directories exist for the orchestrator/tasks
# This might also be done at app startup, but good to ensure here too if tasks run independently.
os.makedirs(settings.TEMP_PATH, exist_ok=True)
os.makedirs(settings.DOCUMENT_PATH, exist_ok=True)
# Add other directories if used by pipeline (e.g., page_images)
os.makedirs(settings.PAGE_IMAGES_PATH, exist_ok=True)
os.makedirs(settings.METADATA_PATH, exist_ok=True)

@app.task(bind=True, name="pipeline.process_document")
def process_document_task(self, pdf_path: str, original_filename: str, doc_id: str = None):
    """
    Celery task to process a single document through the deduplication pipeline.
    
    Args:
        pdf_path (str): The path to the PDF file to process (e.g., a temporary path).
        original_filename (str): The original name of the uploaded file.
        doc_id (str, optional): A pre-generated document ID. If None, one will be created.

    Returns:
        dict: A dictionary containing the processing status and results.
    """
    logger.info(f"Celery task process_document_task started for: {original_filename} (doc_id: {doc_id}, path: {pdf_path})")
    self.update_state(state='PROGRESS', meta={'current_stage': 'Initialization', 'progress': 5})
    
    orchestrator = PipelineOrchestrator()
    
    try:
        # The orchestrator's process_document method will handle its own detailed logging and status updates.
        # Here, we're mainly concerned with the overall task state for Celery.
        # The orchestrator returns a dict which includes a final 'status' key.
        
        # Note: pdf_path should be accessible by the Celery worker.
        # If files are uploaded to a web server, they might need to be moved to a shared location
        # or handled via shared storage (e.g., S3, NFS) if workers are on different machines.
        
        self.update_state(state='PROGRESS', meta={'current_stage': 'Starting Pipeline', 'progress': 10})
        result = orchestrator.process_document(
            pdf_path=pdf_path, 
            original_filename=original_filename, 
            doc_id=doc_id
        )
        
        final_pipeline_status = result.get("status", "unknown_error")
        
        if "error" in final_pipeline_status.lower():
            logger.error(f"Pipeline processing failed for {original_filename}. Result: {result}")
            # The orchestrator should have logged specifics and updated DB status.
            # Update Celery task state to FAILURE.
            self.update_state(state='FAILURE', meta={
                'current_stage': 'Pipeline Error',
                'progress': 100, 
                'error_message': result.get('message', 'Pipeline execution failed.'),
                'details': result
            })
            # Optionally, raise an exception to mark task as failed if not using custom states
            # raise Exception(f"Pipeline failed: {result.get('message')}")
            return result # Return the error result from orchestrator
        else:
            logger.info(f"Pipeline processing successful for {original_filename}. Status: {final_pipeline_status}")
            self.update_state(state='SUCCESS', meta={
                'current_stage': 'Completed', 
                'progress': 100,
                'final_status': final_pipeline_status,
                'details': result
            })
            return result # Return the success result from orchestrator

    except Exception as e:
        logger.exception(f"Critical unhandled error in process_document_task for {original_filename}: {e}")
        self.update_state(state='FAILURE', meta={
            'current_stage': 'Critical Task Error', 
            'progress': 100, 
            'error_message': str(e)
        })
        # Re-raise the exception to ensure Celery marks it as a failure if not using custom states
        raise 