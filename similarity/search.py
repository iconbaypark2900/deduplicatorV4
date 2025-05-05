"""
Similarity search functions using vector indexes.
Provides methods for both FAISS-based and in-memory similarity search.
"""

import os
import json
import numpy as np
import faiss
from typing import List, Dict, Optional, Tuple, Union, Any
import logging

from utils.config import settings

# Set up logging
logger = logging.getLogger(__name__)

# File paths for FAISS index persistence
INDEX_FILE = "storage/metadata/faiss_index.bin"
ID_MAPPING_FILE = "storage/metadata/faiss_id_to_file.json"

# Ensure paths exist
os.makedirs("storage/metadata", exist_ok=True)


def compute_similarity(vec1: List[float], vec2: List[float]) -> float:
    """
    Compute cosine similarity between two vectors.
    
    Args:
        vec1: First vector
        vec2: Second vector
        
    Returns:
        Cosine similarity score (0-1)
    """
    # Convert to numpy arrays
    v1 = np.array(vec1)
    v2 = np.array(vec2)
    
    # Handle zero vectors
    if np.all(v1 == 0) or np.all(v2 == 0):
        return 0.0
    
    # Normalize vectors
    v1_norm = v1 / (np.linalg.norm(v1) + 1e-10)
    v2_norm = v2 / (np.linalg.norm(v2) + 1e-10)
    
    # Compute cosine similarity
    sim = np.dot(v1_norm, v2_norm)
    
    # Ensure value is in valid range
    return float(max(0.0, min(1.0, sim)))


def create_faiss_index(dimension: int = None) -> faiss.Index:
    """
    Create a new FAISS index for vector similarity search.
    
    Args:
        dimension: Dimensionality of the vectors
        
    Returns:
        FAISS index
    """
    if dimension is None:
        dimension = settings.VECTOR_DIMENSION
    
    # Create L2 normalized index for cosine similarity
    index = faiss.IndexFlatIP(dimension)  # Inner product index (for normalized vectors)
    
    return index


def load_or_create_index() -> faiss.Index:
    """
    Load the FAISS index from file or create a new one.
    
    Returns:
        FAISS index
    """
    if os.path.exists(INDEX_FILE):
        try:
            logger.info(f"Loading FAISS index from {INDEX_FILE}")
            index = faiss.read_index(INDEX_FILE)
            return index
        except Exception as e:
            logger.error(f"Error loading FAISS index: {e}")
    
    logger.info("Creating new FAISS index")
    return create_faiss_index()


def save_index(index: faiss.Index) -> None:
    """
    Save the FAISS index to file.
    
    Args:
        index: FAISS index to save
    """
    try:
        logger.info(f"Saving FAISS index to {INDEX_FILE}")
        faiss.write_index(index, INDEX_FILE)
    except Exception as e:
        logger.error(f"Error saving FAISS index: {e}")


def load_id_mapping() -> Dict[str, str]:
    """
    Load the ID mapping from file.
    
    Returns:
        Dictionary mapping IDs to document names
    """
    if os.path.exists(ID_MAPPING_FILE):
        try:
            with open(ID_MAPPING_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading ID mapping: {e}")
    
    return {}


def save_id_mapping(id_mapping: Dict[str, str]) -> None:
    """
    Save the ID mapping to file.
    
    Args:
        id_mapping: Dictionary mapping IDs to document names
    """
    try:
        with open(ID_MAPPING_FILE, "w") as f:
            json.dump(id_mapping, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving ID mapping: {e}")


def add_to_index(index: faiss.Index, vector: List[float], doc_id: str) -> int:
    """
    Add a vector to the FAISS index.
    
    Args:
        index: FAISS index
        vector: Vector to add
        doc_id: Document identifier
        
    Returns:
        Index ID of the added vector
    """
    # Convert to numpy array and reshape
    vector_np = np.array(vector).astype('float32').reshape(1, -1)
    
    # Normalize vector for cosine similarity
    faiss.normalize_L2(vector_np)
    
    # Get next ID
    id_mapping = load_id_mapping()
    next_id = len(id_mapping)
    
    # Add to index
    index.add(vector_np)
    
    # Update ID mapping
    id_mapping[str(next_id)] = doc_id
    save_id_mapping(id_mapping)
    
    # Save the updated index
    save_index(index)
    
    return next_id


def search_index(index: faiss.Index, query_vector: List[float], k: int = 5) -> Tuple[List[float], List[int]]:
    """
    Search the FAISS index for similar vectors.
    
    Args:
        index: FAISS index
        query_vector: Query vector
        k: Number of results to return
        
    Returns:
        Tuple of (distances, indices)
    """
    if index.ntotal == 0:
        logger.warning("Searching empty index")
        return [], []
    
    # Limit k to the number of vectors in the index
    k = min(k, index.ntotal)
    
    # Convert to numpy array and reshape
    query_np = np.array(query_vector).astype('float32').reshape(1, -1)
    
    # Normalize for cosine similarity
    faiss.normalize_L2(query_np)
    
    # Search the index
    distances, indices = index.search(query_np, k)
    
    # Convert to lists
    return distances[0].tolist(), indices[0].tolist()


def find_similar_documents(query_vector: List[float], threshold: float = 0.85, k: int = 5) -> List[Dict[str, Any]]:
    """
    Find similar documents to the query vector.
    
    Args:
        query_vector: Query vector
        threshold: Similarity threshold
        k: Number of results to return
        
    Returns:
        List of dictionaries with matched document information
    """
    # Load index
    index = load_or_create_index()
    
    # Search index
    distances, indices = search_index(index, query_vector, k)
    
    # Load ID mapping
    id_mapping = load_id_mapping()
    
    # Format results
    results = []
    for i, idx in enumerate(indices):
        if distances[i] >= threshold:
            doc_id = id_mapping.get(str(idx))
            if doc_id:
                results.append({
                    "doc_id": doc_id,
                    "similarity": float(distances[i])
                })
    
    return results


def batch_search(vectors: List[List[float]], k: int = 5) -> List[Tuple[List[float], List[int]]]:
    """
    Search the FAISS index for multiple query vectors.
    
    Args:
        vectors: List of query vectors
        k: Number of results to return per query
        
    Returns:
        List of tuples of (distances, indices) for each query
    """
    # Load index
    index = load_or_create_index()
    
    if index.ntotal == 0:
        logger.warning("Searching empty index")
        return [([],  []) for _ in vectors]
    
    # Limit k to the number of vectors in the index
    k = min(k, index.ntotal)
    
    # Convert to numpy array
    queries_np = np.array(vectors).astype('float32')
    
    # Normalize for cosine similarity
    faiss.normalize_L2(queries_np)
    
    # Search the index
    distances, indices = index.search(queries_np, k)
    
    # Convert to list of tuples
    return [(distances[i].tolist(), indices[i].tolist()) for i in range(len(vectors))]