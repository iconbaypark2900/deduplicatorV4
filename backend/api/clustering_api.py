import logging
from fastapi import APIRouter, HTTPException, Depends

# Assuming ClusteringService is in backend.services.clustering_service
# Adjust the import path if your service is located elsewhere.
from backend.services.clustering_service import ClusteringService
from utils.database import get_db # If your service needs a db session passed explicitly
from sqlalchemy.orm import Session # For type hinting if needed

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/clustering", tags=["Clustering"])

@router.post("/trigger_full_db_scan", summary="Trigger Full Database DBSCAN Clustering")
async def trigger_full_db_scan_endpoint():
    """
    Triggers a full DBSCAN clustering process on all relevant documents
    currently stored and processed in the database.

    This process involves:
    1. Fetching TF-IDF vectors for documents from the database.
    2. Running the DBSCAN algorithm.
    3. Storing the resulting cluster assignments back into the database.

    The response will summarize the outcome of the clustering process.
    """
    logger.info("Received request to trigger full database DBSCAN clustering.")
    
    try:
        # Instantiate the service
        # If ClusteringService constructor or its methods require a db session,
        # you might need to pass it: clustering_service = ClusteringService(db=db_session_from_depends)
        clustering_service = ClusteringService()
        
        # Call the method that runs the full clustering process
        # This method is expected to handle DB interactions internally (fetch vectors, store results)
        results = clustering_service.run_dbscan_clustering()
        
        if not results:
            logger.warning("Clustering service returned no results or an empty response.")
            raise HTTPException(status_code=500, detail="Clustering process completed but returned no results.")

        logger.info(f"Full database clustering completed successfully. Results: {results.get('message', 'No message')}")
        return results

    except HTTPException:
        # Re-raise HTTPException if it's already one (e.g., from within the service if it raises them)
        raise
    except Exception as e:
        logger.error(f"Error during full database DBSCAN clustering: {str(e)}", exc_info=True)
        # It's good practice to not expose raw error messages to the client in production.
        # Consider a more generic error message for unexpected issues.
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during the clustering process: {str(e)}")

# Example of how you might include a DB session if the service needed it directly,
# though the current ClusteringService seems to manage its own DB sessions via get_db() context manager.
# @router.post("/trigger_full_db_scan_with_db", summary="Trigger Full DB Scan (with explicit DB session)")
# async def trigger_full_db_scan_endpoint_with_db(db: Session = Depends(get_db)):
#     logger.info("Received request to trigger full database DBSCAN clustering (with explicit DB session).")
#     try:
#         clustering_service = ClusteringService() # Or ClusteringService(db=db) if constructor takes it
#         results = clustering_service.run_dbscan_clustering(db=db) # if run_dbscan_clustering takes db
#         
#         if not results:
#             raise HTTPException(status_code=500, detail="Clustering process returned no results.")
#         return results
#     except Exception as e:
#         logger.error(f"Error during full database DBSCAN clustering: {str(e)}", exc_info=True)
#         raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}") 