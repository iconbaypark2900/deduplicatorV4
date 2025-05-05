"""
Text embedding generation for document similarity.
Uses sentence-transformers to create semantic embeddings of text.
"""

import os
import numpy as np
from typing import List, Dict, Optional, Union
import logging
import pickle
from sentence_transformers import SentenceTransformer

from utils.config import settings

# Set up logging
logger = logging.getLogger(__name__)

# File paths for embedding model persistence
MODEL_CACHE_PATH = "storage/metadata/embedding_model.pkl"

# Global model instance
MODEL = None


def _load_model() -> SentenceTransformer:
    """
    Load the sentence transformer model from file or initialize it.
    Uses caching to avoid reloading the model for each embedding.
    
    Returns:
        SentenceTransformer model
    """
    global MODEL
    
    if MODEL is not None:
        return MODEL
    
    model_name = settings.EMBEDDING_MODEL
    
    try:
        logger.info(f"Loading embedding model: {model_name}")
        MODEL = SentenceTransformer(model_name)
        return MODEL
    except Exception as e:
        logger.error(f"Error loading embedding model: {e}")
        raise


def embed_text(text: str) -> List[float]:
    """
    Convert text into an embedding vector using the sentence transformer model.
    
    Args:
        text: Text to embed
        
    Returns:
        Embedding vector
        
    Raises:
        ValueError: If the text is empty or model initialization fails
    """
    if not text or not text.strip():
        logger.warning("Attempted to embed empty text")
        return np.zeros(settings.VECTOR_DIMENSION).tolist()
    
    try:
        model = _load_model()
        embedding = model.encode(text)
        return embedding.tolist()
    except Exception as e:
        logger.error(f"Error embedding text: {e}")
        # Return zeros vector as fallback
        return np.zeros(settings.VECTOR_DIMENSION).tolist()


def embed_pages(pages: List[str]) -> List[List[float]]:
    """
    Convert multiple pages of text into embedding vectors.
    More efficient than calling embed_text repeatedly.
    
    Args:
        pages: List of text pages to embed
        
    Returns:
        List of embedding vectors
    """
    if not pages:
        return []
    
    # Filter out empty pages
    valid_pages = [page for page in pages if page and page.strip()]
    
    if not valid_pages:
        return [np.zeros(settings.VECTOR_DIMENSION).tolist() for _ in pages]
    
    try:
        model = _load_model()
        embeddings = model.encode(valid_pages)
        
        # Map back to original pages list, using zeros for empty pages
        result = []
        valid_idx = 0
        
        for page in pages:
            if page and page.strip():
                result.append(embeddings[valid_idx].tolist())
                valid_idx += 1
            else:
                result.append(np.zeros(settings.VECTOR_DIMENSION).tolist())
        
        return result
    except Exception as e:
        logger.error(f"Error embedding pages: {e}")
        # Return zeros vectors as fallback
        return [np.zeros(settings.VECTOR_DIMENSION).tolist() for _ in pages]


def compare_embeddings(emb1: List[float], emb2: List[float]) -> float:
    """
    Compare two embedding vectors using cosine similarity.
    
    Args:
        emb1: First embedding vector
        emb2: Second embedding vector
        
    Returns:
        Cosine similarity (0-1)
    """
    if not emb1 or not emb2:
        return 0.0
    
    # Convert to numpy arrays
    vec1 = np.array(emb1)
    vec2 = np.array(emb2)
    
    # Normalize vectors
    vec1_norm = vec1 / (np.linalg.norm(vec1) + 1e-10)
    vec2_norm = vec2 / (np.linalg.norm(vec2) + 1e-10)
    
    # Compute cosine similarity
    similarity = np.dot(vec1_norm, vec2_norm)
    return float(similarity)


def embed_chunks(text: str, chunk_size: int = 1000, overlap: int = 100) -> List[List[float]]:
    """
    Split text into overlapping chunks and embed each chunk.
    Useful for very long documents.
    
    Args:
        text: Text to embed
        chunk_size: Size of each chunk in characters
        overlap: Overlap between chunks in characters
        
    Returns:
        List of embedding vectors for each chunk
    """
    if not text:
        return []
    
    # Split into chunks
    chunks = []
    words = text.split()
    
    current_chunk = []
    current_length = 0
    
    for word in words:
        current_chunk.append(word)
        current_length += len(word) + 1  # +1 for space
        
        if current_length >= chunk_size:
            chunks.append(" ".join(current_chunk))
            
            # Keep overlap words
            overlap_words = int(overlap / 5)  # Approximate number of words in overlap
            current_chunk = current_chunk[-overlap_words:] if overlap_words > 0 else []
            current_length = sum(len(w) + 1 for w in current_chunk)
    
    # Add final chunk if non-empty
    if current_chunk:
        chunks.append(" ".join(current_chunk))
    
    # Embed all chunks
    return embed_pages(chunks)