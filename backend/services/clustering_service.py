# backend/services/clustering_service.py
import logging
import numpy as np
from sklearn.cluster import DBSCAN
# from sklearn.metrics.pairwise import cosine_similarity # DBSCAN with metric='cosine' handles this

# Assuming your modified similarity.tfidf module has a function to get vectors
# This import will depend on the final structure of your modified tfidf.py
# from similarity.tfidf import get_all_document_vectors # Placeholder, actual fetching to be wired
from utils.database import get_db, DocumentVector # For actual DB operations later
from sqlalchemy.orm import Session # For type hinting

from utils.config import settings 

logger = logging.getLogger(__name__)

class ClusteringService:
    def __init__(self):
        # DBSCAN eps is a distance. If CLUSTER_THRESHOLD is a similarity (0 to 1),
        # then eps = 1 - similarity. Let's assume settings.CLUSTER_THRESHOLD is a similarity.
        # If CLUSTER_THRESHOLD is already a distance, then this conversion is not needed.
        # For cosine distance, smaller eps means documents must be more similar.
        self.dbscan_eps = 1.0 - settings.CLUSTER_THRESHOLD  # e.g., if threshold is 0.75 similarity, eps is 0.25 distance
        if not (0 < self.dbscan_eps < 1):
            logger.warning(f"Calculated DBSCAN eps ({self.dbscan_eps}) is outside typical (0,1) range for cosine distance. Check CLUSTER_THRESHOLD ({settings.CLUSTER_THRESHOLD}). Defaulting eps to 0.5")
            self.dbscan_eps = 0.5 # A default fallback

        self.dbscan_min_samples = settings.MIN_CLUSTER_SIZE
        
        logger.info(f"ClusteringService initialized with DBSCAN eps: {self.dbscan_eps}, min_samples: {self.dbscan_min_samples}")


    def _fetch_tfidf_vectors(self) -> tuple[list[str], np.ndarray | None]:
        """
        Fetches all TF-IDF vectors and their corresponding document IDs.
        Currently uses mock data. Replace with actual DB call to similarity.tfidf.get_all_document_vectors.
        """
        logger.info("Fetching TF-IDF vectors... (Using MOCK DATA for now)")
        
        # MOCK DATA - Replace with actual database fetching logic
        # This should ideally call a function that gets vectors for a specific batch/set of documents
        # relevant to the current clustering request, not necessarily *all* vectors in the DB
        # unless that's the desired behavior (e.g., re-clustering everything).

        # For now, using a placeholder similar to what was in the prompt
        # This would eventually use:
        # with get_db() as db:
        #     all_vectors_data = get_all_document_vectors(db, 'tfidf') # from similarity.tfidf
        # if not all_vectors_data:
        #     return [], None
        # doc_ids = [item[0] for item in all_vectors_data]
        # vector_matrix = np.array([item[1] for item in all_vectors_data])
        # if vector_matrix.ndim == 1: # Handle case of single vector
        #     vector_matrix = vector_matrix.reshape(1, -1)
        
        # Using simple mock data for structure:
        num_docs = np.random.randint(5, 20) # Random number of docs
        num_features = np.random.randint(50, 200) # Random number of TF-IDF features
        
        if num_docs < self.dbscan_min_samples:
            logger.warning(f"Mock data generated only {num_docs} docs, less than min_samples {self.dbscan_min_samples}. Clustering might be trivial.")

        mock_doc_ids = [f"mock_doc_{i+1}" for i in range(num_docs)]
        # Simulating TF-IDF vectors (typically sparse, but DBSCAN needs dense or specific sparse support)
        # Scikit-learn's DBSCAN with metric='cosine' can handle dense arrays.
        mock_vectors = np.random.rand(num_docs, num_features) 
        
        if not mock_doc_ids:
             return [], None
        logger.info(f"Mock data: {len(mock_doc_ids)} documents, {mock_vectors.shape[1] if mock_vectors.size > 0 else 0} features.")
        return mock_doc_ids, mock_vectors

    def _store_cluster_assignments(self, db: Session, doc_ids: list[str], cluster_labels: np.ndarray):
        """
        Stores the assigned cluster ID for each document in the database.
        Placeholder: Logs assignments. Actual DB update needed.
        """
        logger.info(f"Attempting to store cluster assignments for {len(doc_ids)} documents.")
        assignments = []
        for doc_id, label in zip(doc_ids, cluster_labels):
            cluster_id_str = f"cluster_{label}" if label != -1 else "outlier"
            assignments.append({"doc_id": doc_id, "cluster_id": cluster_id_str})
            
            # Actual database update logic:
            # try:
            #     # Assuming Document is your metadata table with a 'cluster_id' field
            #     # Or you might have a separate DocumentClusterAssignment table
            #     stmt = update(Document).where(Document.id == doc_id).values(cluster_id=cluster_id_str)
            #     db.execute(stmt)
            # except Exception as e:
            #     logger.error(f"Failed to update cluster_id for {doc_id}: {e}")
            
        # db.commit() # Commit after all updates
        logger.debug(f"Cluster assignments (first 5): {assignments[:5]}")
        logger.info("DB storage for cluster assignments is a placeholder. Actual implementation needed.")


    def run_dbscan_clustering(self) -> dict:
        """
        Retrieves TF-IDF vectors, runs DBSCAN, stores assignments (placeholder), and returns results.
        """
        doc_ids, vector_matrix = self._fetch_tfidf_vectors()

        if vector_matrix is None or vector_matrix.shape[0] < self.dbscan_min_samples :
            logger.warning(f"Not enough document vectors ({vector_matrix.shape[0] if vector_matrix is not None else 0} found) to perform clustering (min_samples: {self.dbscan_min_samples}).")
            return {"message": "Not enough data for clustering.", "clusters": [], "nodes_for_visualization": [], "total_documents": 0, "num_clusters":0, "num_outliers":0}

        logger.info(f"Running DBSCAN on {vector_matrix.shape[0]} documents with eps={self.dbscan_eps}, min_samples={self.dbscan_min_samples}, metric='cosine'")

        try:
            dbscan = DBSCAN(eps=self.dbscan_eps, min_samples=self.dbscan_min_samples, metric="cosine")
            cluster_labels = dbscan.fit_predict(vector_matrix)
        except Exception as e:
            logger.error(f"DBSCAN fit_predict failed: {e}", exc_info=True)
            return {"message": f"Clustering algorithm failed: {e}", "clusters": [], "nodes_for_visualization": [], "total_documents": len(doc_ids), "num_clusters":0, "num_outliers":len(doc_ids)}


        # Placeholder for DB session for storing assignments
        # with get_db() as db:
        #    self._store_cluster_assignments(db, doc_ids, cluster_labels)
        logger.info("Calling placeholder for _store_cluster_assignments.")
        self._store_cluster_assignments(None, doc_ids, cluster_labels) # Passing None as db for now

        num_clusters = len(set(label for label in cluster_labels if label != -1))
        num_outliers = np.sum(cluster_labels == -1)

        logger.info(f"Clustering complete: {num_clusters} clusters found, {num_outliers} outliers.")

        nodes = [{
            "doc_id": doc_id, 
            "filename": doc_id, # Placeholder, filename might need to be fetched alongside vectors
            "cluster_id": f"cluster_{label}" if label != -1 else "outlier"
            } for doc_id, label in zip(doc_ids, cluster_labels)]

        cluster_summary = []
        if num_clusters > 0:
            for label_id in sorted(list(set(l for l in cluster_labels if l != -1))):
                docs_in_cluster = [doc_ids[i] for i, lbl in enumerate(cluster_labels) if lbl == label_id]
                cluster_summary.append({
                    "cluster_id": f"cluster_{label_id}",
                    "documents": docs_in_cluster,
                    "doc_count": len(docs_in_cluster)
                })
        
        return {
            "message": "Clustering successful (using mock data and placeholder storage)",
            "total_documents": len(doc_ids),
            "num_clusters": num_clusters,
            "num_outliers": num_outliers,
            "clusters": cluster_summary, 
            "nodes_for_visualization": nodes 
        }

# Example of how this service might be triggered 
# (e.g., by a Celery task or an admin API)
# def trigger_clustering_update():
# service = ClusteringService()
# results = service.run_dbscan_clustering()
# logger.info(f"Clustering update triggered, results: {results.get('message')}")
# return results 