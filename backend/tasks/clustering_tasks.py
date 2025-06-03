# backend/tasks/clustering_tasks.py
import logging
from backend.celery_app import app
from backend.services.clustering_service import ClusteringService

logger = logging.getLogger(__name__)

@app.task(name="clustering.run_dbscan")
def run_clustering_task():
    """
    Celery task to run DBSCAN clustering.
    This task is typically triggered periodically or after a batch of documents 
    has been processed and their TF-IDF vectors stored.
    """
    logger.info("Celery task run_clustering_task started.")
    try:
        service = ClusteringService()
        results = service.run_dbscan_clustering()
        
        logger.info(f"Clustering task completed. Message: {results.get('message')}")
        logger.info(f"Clusters found: {results.get('num_clusters')}, Outliers: {results.get('num_outliers')}")
        # Further actions can be taken here, like notifying an admin,
        # or storing aggregated stats, though the service itself handles individual assignments.
        return {
            "status": "SUCCESS",
            "message": results.get('message'),
            "num_clusters": results.get('num_clusters'),
            "num_outliers": results.get('num_outliers'),
            "total_documents_processed_in_batch": results.get('total_documents')
        }
    except Exception as e:
        logger.exception("Critical error in run_clustering_task.")
        # Optionally, re-raise to mark the task as FAILED in Celery
        # For now, just logging and returning an error status
        return {
            "status": "FAILURE",
            "error": str(e)
        } 