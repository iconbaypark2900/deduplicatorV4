"""
Document and page hashing utilities for exact duplicate detection.
Provides functions for various hashing strategies.
"""

import hashlib
import re
import os
from typing import List, Dict, Optional, Set, Tuple, Any
import logging
from datasketch import MinHash, MinHashLSH

from ingestion.pdf_reader import extract_text_from_pdf, extract_pages_from_pdf

# Set up logging
logger = logging.getLogger(__name__)

# Constants
NUM_PERM = 128  # Number of permutations for MinHash
JACCARD_THRESHOLD = 0.8  # Default similarity threshold for LSH


def compute_document_hash(pdf_path: str) -> Optional[str]:
    """
    Compute a SHA-256 hash of the document text.
    Used for exact duplicate detection.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        Hash string or None if extraction fails
    """
    try:
        # Extract text
        text = extract_text_from_pdf(pdf_path)
        if not text:
            logger.warning(f"No text extracted from {pdf_path}")
            return None
        
        # Normalize and hash
        normalized_text = normalize_for_hash(text)
        return hashlib.sha256(normalized_text.encode('utf-8')).hexdigest()
    except Exception as e:
        logger.error(f"Error computing document hash: {e}")
        return None


def compute_page_hash(page_text: str) -> str:
    """
    Compute a SHA-256 hash of the page text.
    Used for exact duplicate page detection.
    
    Args:
        page_text: Text content of the page
        
    Returns:
        Hash string
    """
    normalized_text = normalize_for_hash(page_text)
    return hashlib.sha256(normalized_text.encode('utf-8')).hexdigest()


def normalize_for_hash(text: str) -> str:
    """
    Normalize text for hashing to ensure consistent results.
    Removes whitespace, punctuation, and converts to lowercase.
    
    Args:
        text: Text to normalize
        
    Returns:
        Normalized text
    """
    if not text:
        return ""
    
    # Convert to lowercase
    text = text.lower()
    
    # Remove whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Remove punctuation except hyphens (important for medical terms)
    text = re.sub(r'[^\w\s-]', '', text)
    
    # Final trimming
    return text.strip()


def get_minhash(text: str, num_perm: int = NUM_PERM) -> MinHash:
    """
    Create a MinHash object for the document text.
    Used for approximate similarity comparison.
    
    Args:
        text: Document text
        num_perm: Number of permutations for MinHash
        
    Returns:
        MinHash object
    """
    m = MinHash(num_perm=num_perm)
    
    # Create shingles (3-word sequences)
    words = text.split()
    for i in range(len(words) - 2):
        shingle = " ".join(words[i:i+3])
        m.update(shingle.encode('utf-8'))
        
    return m


def create_lsh_index(threshold: float = JACCARD_THRESHOLD, num_perm: int = NUM_PERM) -> MinHashLSH:
    """
    Create a Locality-Sensitive Hashing (LSH) index for fast similarity search.
    
    Args:
        threshold: Jaccard similarity threshold
        num_perm: Number of permutations for MinHash
        
    Returns:
        LSH index
    """
    return MinHashLSH(threshold=threshold, num_perm=num_perm)


def add_to_lsh_index(lsh_index: MinHashLSH, doc_id: str, minhash: MinHash) -> None:
    """
    Add a document to the LSH index.
    
    Args:
        lsh_index: LSH index
        doc_id: Document identifier
        minhash: MinHash object for the document
    """
    lsh_index.insert(doc_id, minhash)


def query_lsh_index(lsh_index: MinHashLSH, minhash: MinHash) -> List[str]:
    """
    Query the LSH index for similar documents.
    
    Args:
        lsh_index: LSH index
        minhash: MinHash object for the query
        
    Returns:
        List of similar document IDs
    """
    return lsh_index.query(minhash)


def compute_page_hashes(pdf_path: str) -> List[str]:
    """
    Compute hashes for all pages in a document.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        List of page hashes
    """
    try:
        pages = extract_pages_from_pdf(pdf_path)
        if not pages:
            logger.warning(f"No pages extracted from {pdf_path}")
            return []
        
        return [compute_page_hash(page) for page in pages]
    except Exception as e:
        logger.error(f"Error computing page hashes: {e}")
        return []


def detect_common_pages(hashes1: List[str], hashes2: List[str]) -> List[Tuple[int, int]]:
    """
    Detect common pages between two documents using hashes.
    
    Args:
        hashes1: List of page hashes for first document
        hashes2: List of page hashes for second document
        
    Returns:
        List of tuples (page_index1, page_index2) for matching pages
    """
    common_pages = []
    
    for i, hash1 in enumerate(hashes1):
        for j, hash2 in enumerate(hashes2):
            if hash1 == hash2:
                common_pages.append((i, j))
    
    return common_pages


def fingerprint_document(pdf_path: str) -> Dict[str, Any]:
    """
    Create a comprehensive fingerprint of a document.
    Includes hash, page hashes, and MinHash representation.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        Dictionary with document fingerprint data
    """
    try:
        # Extract text
        text = extract_text_from_pdf(pdf_path)
        if not text:
            logger.warning(f"No text extracted from {pdf_path}")
            return {"error": "No text extracted"}
        
        # Get document hash
        doc_hash = compute_document_hash(pdf_path)
        
        # Get page hashes
        pages = extract_pages_from_pdf(pdf_path)
        page_hashes = [compute_page_hash(page) for page in pages if page]
        
        # Get MinHash
        minhash = get_minhash(text)
        
        return {
            "hash": doc_hash,
            "page_hashes": page_hashes,
            "minhash": minhash,
            "num_pages": len(pages)
        }
    except Exception as e:
        logger.error(f"Error creating document fingerprint: {e}")
        return {"error": str(e)}