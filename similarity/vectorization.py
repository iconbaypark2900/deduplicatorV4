"""
Vectorization strategies for document similarity.
Implements the strategy pattern for different text vectorization approaches.
"""

from abc import ABC, abstractmethod
import numpy as np
from typing import List


class VectorizationStrategy(ABC):
    """
    Abstract base class for vectorization strategies.
    Defines the interface that all concrete strategies must implement.
    """
    
    @abstractmethod
    def vectorize(self, text: str) -> np.ndarray:
        """
        Convert text to vector representation.
        
        Args:
            text: The text to vectorize
            
        Returns:
            Vector representation of the text
        """
        pass
    
    @abstractmethod
    def vectorize_batch(self, texts: List[str]) -> List[np.ndarray]:
        """
        Convert multiple texts to vector representations.
        
        Args:
            texts: List of texts to vectorize
            
        Returns:
            List of vector representations
        """
        pass
    
    @abstractmethod
    def update_corpus(self, text: str, doc_name: str) -> None:
        """
        Update the corpus with a new document.
        
        Args:
            text: Document text
            doc_name: Document identifier
        """
        pass


class TFIDFStrategy(VectorizationStrategy):
    """
    TF-IDF based vectorization strategy.
    Uses term frequency-inverse document frequency for text representation.
    """
    
    def __init__(self):
        """Initialize the TF-IDF strategy."""
        from similarity.tfidf import (
            tfidf_vectorize, 
            update_tfidf_corpus
        )
        self._vectorize = tfidf_vectorize
        self._update_corpus = update_tfidf_corpus
    
    def vectorize(self, text: str) -> np.ndarray:
        """
        Convert text to TF-IDF vector.
        
        Args:
            text: The text to vectorize
            
        Returns:
            TF-IDF vector
        """
        return self._vectorize(text)
    
    def vectorize_batch(self, texts: List[str]) -> List[np.ndarray]:
        """
        Convert multiple texts to TF-IDF vectors.
        
        Args:
            texts: List of texts to vectorize
            
        Returns:
            List of TF-IDF vectors
        """
        return [self._vectorize(text) for text in texts]
    
    def update_corpus(self, text: str, doc_name: str) -> None:
        """
        Update the TF-IDF corpus with a new document.
        
        Args:
            text: Document text
            doc_name: Document identifier
        """
        self._update_corpus(text, doc_name)