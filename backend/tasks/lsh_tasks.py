import logging
from ..celery_app import app # Assuming your Celery app instance is here
from similarity.hashing import (
    create_lsh_index, 
    rebuild_lsh_index_from_db, 
    save_lsh_index_instance, # Import from similarity.hashing
    JACCARD_THRESHOLD, # Import from similarity.hashing (was LSH_THRESHOLD)
    NUM_PERM # Import from similarity.hashing (was LSH_NUM_PERM)
)
# from backend.services.pipeline_orchestrator import save_lsh_index_instance, LSH_THRESHOLD, LSH_NUM_PERM # Old import
from utils.database import get_db

logger = logging.getLogger(__name__)

@app.task(name="tasks.rebuild_global_lsh_index")
def rebuild_global_lsh_index_task():
    """
    Periodically rebuilds the global LSH index from all MinHash signatures
    stored in the database and saves it to the LSH_INDEX_FILE.
    """
    logger.info("Starting global LSH index rebuild task...")
    try:
        new_lsh_index = create_lsh_index(threshold=JACCARD_THRESHOLD, num_perm=NUM_PERM)
        with get_db() as db:
            rebuild_lsh_index_from_db(new_lsh_index, db)
        
        save_lsh_index_instance(new_lsh_index) # Now from similarity.hashing
        logger.info("Global LSH index rebuilt and saved successfully.")
    except Exception as e:
        logger.error(f"Error during global LSH index rebuild: {e}", exc_info=True)
        # Depending on your alerting, you might want to raise the exception
        # or notify an admin to investigate. 