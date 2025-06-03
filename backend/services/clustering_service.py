# backend/services/clustering_service.py
import logging
import numpy as np
from sklearn.cluster import DBSCAN
# from sklearn.metrics.pairwise import cosine_similarity # DBSCAN with metric='cosine' handles this

# Assuming your modified similarity.tfidf module has a function to get vectors
from similarity.tfidf import get_all_document_vectors 
from utils.database import get_db, upsert_document_metadata, DocumentMetadata # Added DocumentMetadata for filename fetching
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


    def _fetch_tfidf_vectors(self) -> tuple[list[str], list[str], np.ndarray | None]:
        """
        Fetches all TF-IDF vectors, their corresponding document IDs, and filenames from the database.
        Returns: 
            A tuple containing (list of document_ids, list of filenames, NumPy matrix of vectors)
            Returns ([], [], None) if no data or error.
        """
        logger.info("Fetching TF-IDF vectors and filenames from database...")
        
        doc_ids_from_vectors = []
        vectors_list = []
        filenames_map = {}

        try:
            with get_db() as db:
                # Step 1: Get all document vectors
                all_vectors_data = get_all_document_vectors(db, vector_type='tfidf')
            
                if not all_vectors_data:
                    logger.warning("No TF-IDF vectors found in the database.")
                    return [], [], None

                for doc_id, vector_array in all_vectors_data:
                    if vector_array is not None and vector_array.size > 0:
                        doc_ids_from_vectors.append(doc_id)
                        vectors_list.append(vector_array)
                    else:
                        logger.warning(f"Document {doc_id} has an empty or None vector. Skipping for clustering.")

                if not vectors_list:
                    logger.warning("No valid vectors found after filtering. Cannot perform clustering.")
                    return [], [], None

                # Step 2: Get filenames for the doc_ids that have vectors
                if doc_ids_from_vectors:
                    metadata_records = db.query(DocumentMetadata.doc_id, DocumentMetadata.filename).filter(DocumentMetadata.doc_id.in_(doc_ids_from_vectors)).all()
                    filenames_map = {record.doc_id: record.filename for record in metadata_records}

            # Prepare final lists, ensuring order matches
            final_doc_ids = []
            final_filenames = []
            final_vectors_list = []

            for i, doc_id in enumerate(doc_ids_from_vectors):
                filename = filenames_map.get(doc_id)
                if filename:
                    final_doc_ids.append(doc_id)
                    final_filenames.append(filename)
                    final_vectors_list.append(vectors_list[i])
                else:
                    logger.warning(f"Filename not found for doc_id {doc_id}. This document will be excluded from clustering.")
            
            if not final_vectors_list:
                logger.warning("No documents with both valid vectors and filenames found. Cannot perform clustering.")
                return [], [], None

            vector_matrix = np.array(final_vectors_list)
            
            if vector_matrix.ndim == 1 and len(final_vectors_list) == 1:
                 vector_matrix = vector_matrix.reshape(1, -1)
            elif vector_matrix.ndim == 1 and len(final_vectors_list) > 1:
                logger.error(f"Vector matrix is 1D but contains {len(final_vectors_list)} vectors. This indicates inconsistent vector shapes or an issue in data.")
                try:
                    vector_matrix = np.vstack(final_vectors_list)
                except ValueError as ve:
                    logger.error(f"Failed to stack vectors into a matrix due to shape inconsistency: {ve}")
                    return [], [], None

            logger.info(f"Fetched {len(final_doc_ids)} documents with TF-IDF vectors and filenames. Matrix shape: {vector_matrix.shape}")
            return final_doc_ids, final_filenames, vector_matrix

        except Exception as e:
            logger.error(f"Error fetching TF-IDF vectors or filenames from database: {e}", exc_info=True)
            return [], [], None

    def _store_cluster_assignments(self, db: Session, doc_ids: list[str], cluster_labels: np.ndarray):
        """
        Stores the assigned cluster ID for each document in the DocumentMetadata table.
        """
        logger.info(f"Storing cluster assignments for {len(doc_ids)} documents.")
        updated_count = 0
        failed_count = 0
        for doc_id, label in zip(doc_ids, cluster_labels):
            cluster_id_str = f"cluster_{label}" if label != -1 else "outlier"
            try:
                upsert_document_metadata(db, doc_id, cluster_id=cluster_id_str)
                logger.debug(f"Updated cluster_id for {doc_id} to {cluster_id_str}")
                updated_count += 1
            except Exception as e:
                logger.error(f"Failed to update cluster_id for {doc_id}: {e}", exc_info=True)
                failed_count += 1
        
        if failed_count > 0:
            logger.warning(f"Finished storing cluster assignments. Updated: {updated_count}, Failed: {failed_count}")
        else:
            logger.info(f"Successfully stored all {updated_count} cluster assignments.")


    def run_dbscan_clustering(self) -> dict:
        """
        Retrieves TF-IDF vectors, runs DBSCAN, stores assignments, and returns results.
        """
        doc_ids, filenames, vector_matrix = self._fetch_tfidf_vectors()

        if vector_matrix is None or vector_matrix.size == 0 or vector_matrix.shape[0] == 0:
             logger.warning(f"Vector matrix is None, empty, or has no rows. Cannot perform clustering.")
             # Ensure filenames list matches doc_ids if any for visualization, though likely empty
             nodes_for_viz = []
             if doc_ids and filenames and len(doc_ids) == len(filenames):
                 nodes_for_viz = [{"doc_id": did, "filename": fname, "cluster_id": "error_no_vector_data"} for did, fname in zip(doc_ids, filenames)]
             else: # Fallback if doc_ids and filenames are inconsistent or empty
                 nodes_for_viz = [{"doc_id": did, "filename": did, "cluster_id": "error_no_vector_data"} for did in doc_ids] if doc_ids else []

             return {"message": "Not enough data or valid vectors for clustering.", "clusters": [], 
                     "nodes_for_visualization": nodes_for_viz, 
                     "total_documents": len(doc_ids) if doc_ids else 0, "num_clusters":0, "num_outliers":0}


        if vector_matrix.shape[0] < self.dbscan_min_samples :
            logger.warning(f"Not enough document vectors ({vector_matrix.shape[0]} found) to perform clustering (min_samples: {self.dbscan_min_samples}). Assigning all as outliers.")
            with get_db() as db: # Store as outliers
                for doc_id in doc_ids:
                    try:
                        upsert_document_metadata(db, doc_id, cluster_id="outlier_insufficient_data")
                    except Exception as e:
                        logger.error(f"Failed to mark {doc_id} as outlier_insufficient_data: {e}")

            return {
                "message": f"Not enough data for meaningful clustering (got {vector_matrix.shape[0]} docs, need {self.dbscan_min_samples}). All marked as outliers.", 
                "clusters": [], 
                "nodes_for_visualization": [{"doc_id": did, "filename": fname, "cluster_id": "outlier_insufficient_data"} for did, fname in zip(doc_ids, filenames)], 
                "total_documents": len(doc_ids), 
                "num_clusters":0, 
                "num_outliers":len(doc_ids)
            }

        try:
            dbscan = DBSCAN(eps=self.dbscan_eps, min_samples=self.dbscan_min_samples, metric="cosine")
            cluster_labels = dbscan.fit_predict(vector_matrix)
        except ValueError as ve:
            if "Found array with 0 feature(s) (shape=(n_samples, 0))" in str(ve):
                logger.error(f"DBSCAN failed: Input data has 0 features. Vector matrix shape: {vector_matrix.shape}. This might happen if TF-IDF vocab is empty or not fitted.", exc_info=True)
                return {"message": "Clustering algorithm failed: Input data has 0 features.", "clusters": [], "nodes_for_visualization": [], "total_documents": len(doc_ids), "num_clusters":0, "num_outliers":len(doc_ids)}
            logger.error(f"DBSCAN fit_predict failed due to ValueError: {ve}", exc_info=True)
            return {"message": f"Clustering algorithm failed with ValueError: {ve}", "clusters": [], "nodes_for_visualization": [], "total_documents": len(doc_ids), "num_clusters":0, "num_outliers":len(doc_ids)}
        except Exception as e:
            logger.error(f"DBSCAN fit_predict failed: {e}", exc_info=True)
            return {"message": f"Clustering algorithm failed: {e}", "clusters": [], "nodes_for_visualization": [], "total_documents": len(doc_ids), "num_clusters":0, "num_outliers":len(doc_ids)}

        # Placeholder for DB session for storing assignments
        with get_db() as db:
           self._store_cluster_assignments(db, doc_ids, cluster_labels)
        # logger.info("Calling placeholder for _store_cluster_assignments.")
        # self._store_cluster_assignments(None, doc_ids, cluster_labels) # Passing None as db for now

        num_clusters = len(set(label for label in cluster_labels if label != -1))
        num_outliers = np.sum(cluster_labels == -1)

        logger.info(f"Clustering complete: {num_clusters} clusters found, {num_outliers} outliers.")

        nodes = [{
            "doc_id": doc_id, 
            "filename": filename, # Now using actual filename
            "cluster_id": f"cluster_{label}" if label != -1 else "outlier"
            } for doc_id, filename, label in zip(doc_ids, filenames, cluster_labels)]

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

