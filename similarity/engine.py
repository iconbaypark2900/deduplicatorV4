"""
Core similarity engine for document comparison.
Provides unified interface for different similarity methods.
"""

import numpy as np
import os
import json
from typing import List, Dict, Optional, Any, Union

from similarity.vectorization import VectorizationStrategy, TFIDFStrategy


class SimilarityEngine:
    """
    Unified engine for document similarity detection.
    Abstracts different vectorization and comparison strategies.
    """
    
    def __init__(self):
        """
        Initialize the similarity engine for TF-IDF.
        """
        self._ensure_storage_dirs()
        self.vectorizer = self._get_vectorizer()

    def _ensure_storage_dirs(self) -> None:
        """Ensure all necessary storage directories exist."""
        os.makedirs("storage/metadata", exist_ok=True)
        os.makedirs("storage/documents", exist_ok=True)
        os.makedirs("storage/tmp", exist_ok=True)

    def _get_vectorizer(self) -> VectorizationStrategy:
        """
        Get the TF-IDF vectorization strategy.
            
        Returns:
            An instance of TFIDFStrategy
        """
        return TFIDFStrategy()

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
        Find duplicate for document text using TF-IDF.
        
        Args:
            text: Document text to check
            threshold: Similarity threshold for determining duplicates
            
        Returns:
            Dictionary with status and match details if found
        """
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