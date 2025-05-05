"""
Core similarity engine for document comparison.
Provides unified interface for different similarity methods.
"""

import numpy as np
import os
import json
from typing import List, Dict, Optional, Any, Union

from utils.config import settings
from similarity.vectorization import VectorizationStrategy, TFIDFStrategy, EmbeddingStrategy

# Similarity method configuration
SIMILARITY_METHOD = getattr(settings, "SIMILARITY_METHOD", "tfidf")


class SimilarityEngine:
    """
    Unified engine for document similarity detection.
    Abstracts different vectorization and comparison strategies.
    """
    
    def __init__(self, method: str = None):
        """
        Initialize the similarity engine.
        
        Args:
            method: Vectorization method to use ("tfidf" or "embedding")
        """
        self.method = method or SIMILARITY_METHOD
        self._ensure_storage_dirs()
        self.vectorizer = self._get_vectorizer(self.method)

    def _ensure_storage_dirs(self) -> None:
        """Ensure all necessary storage directories exist."""
        os.makedirs("storage/metadata", exist_ok=True)
        os.makedirs("storage/documents", exist_ok=True)
        os.makedirs("storage/tmp", exist_ok=True)

    def _get_vectorizer(self, method: str) -> VectorizationStrategy:
        """
        Get the appropriate vectorization strategy.
        
        Args:
            method: The vectorization method to use
            
        Returns:
            An instance of a VectorizationStrategy
            
        Raises:
            ValueError: If the method is not supported
        """
        if method == "tfidf":
            return TFIDFStrategy()
        elif method == "embedding":
            return EmbeddingStrategy()
        else:
            raise ValueError(f"Unsupported vectorization method: {method}")

    def vectorize(self, text: str) -> np.ndarray:
        """
        Convert text to vector using the configured method.
        
        Args:
            text: The text to vectorize
            
        Returns:
            A vector representation of the text
        """
        return self.vectorizer.vectorize(text)

    def vectorize_batch(self, texts: List[str]) -> List[np.ndarray]:
        """
        Convert multiple texts to vectors using the configured method.
        
        Args:
            texts: List of texts to vectorize
            
        Returns:
            List of vector representations
        """
        return self.vectorizer.vectorize_batch(texts)

    def add_document(self, text: str, doc_name: str) -> None:
        """
        Add a new document to the appropriate storage.
        
        Args:
            text: Document text
            doc_name: Document identifier
        """
        self.vectorizer.update_corpus(text, doc_name)

    def compute_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """
        Compute cosine similarity between two vectors.
        
        Args:
            vec1: First vector
            vec2: Second vector
            
        Returns:
            Cosine similarity score (0-1)
        """
        # Normalize vectors
        vec1_norm = vec1 / (np.linalg.norm(vec1) + 1e-8)
        vec2_norm = vec2 / (np.linalg.norm(vec2) + 1e-8)
        
        # Compute cosine similarity
        similarity = np.dot(vec1_norm, vec2_norm)
        return float(similarity)

    def find_duplicate(self, text: str, threshold: float = 0.85) -> Dict[str, Any]:
        """
        Find duplicate for document text using the configured similarity method.
        
        Args:
            text: Document text to check
            threshold: Similarity threshold for determining duplicates
            
        Returns:
            Dictionary with status and match details if found
            
        Raises:
            ValueError: If the method is not supported
        """
        if self.method == "tfidf":
            from similarity.tfidf import tfidf_search
            
            query_vector = self.vectorize(text)
            match_info = tfidf_search(query_vector, threshold=threshold)
            
            if match_info:
                return {
                    "status": "duplicate",
                    "details": match_info
                }
            return {
                "status": "unique",
                "details": None
            }
        elif self.method == "embedding":
            from similarity.search import search_index, load_or_create_index
            
            vector = self.vectorize(text)
            index = load_or_create_index()
            distances, indices = search_index(index, vector.tolist())
            
            if len(indices) > 0 and distances[0] >= threshold:
                # Look up the document name from the index
                with open("storage/metadata/faiss_id_to_file.json", "r") as f:
                    id_map = json.load(f)
                    doc_id = str(indices[0])
                    
                    if doc_id in id_map:
                        return {
                            "status": "duplicate",
                            "details": {
                                "matched_doc": id_map[doc_id],
                                "similarity": float(distances[0])
                            }
                        }
            
            return {
                "status": "unique",
                "details": None
            }
        else:
            raise ValueError(f"Unsupported method: {self.method}")

    def _get_next_doc_id(self) -> int:
        """
        Get the next available document ID for FAISS index.
        
        Returns:
            Next available document ID
        """
        id_map_file = "storage/metadata/faiss_id_to_file.json"
        if os.path.exists(id_map_file):
            with open(id_map_file, "r") as f:
                id_map = json.load(f)
                
            if id_map:
                return max(int(k) for k in id_map.keys()) + 1
                
        return 0