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
import pickle

from ingestion.pdf_reader import extract_text_from_pdf, extract_pages_from_pdf
from utils.database import DocumentMetadata, get_db
from sqlalchemy.orm import Session
from utils.config import settings

# Set up logging
logger = logging.getLogger(__name__)

# Constants
NUM_PERM = settings.LSH_NUM_PERMUTATIONS if hasattr(settings, 'LSH_NUM_PERMUTATIONS') else 128
JACCARD_THRESHOLD = settings.LSH_JACCARD_THRESHOLD if hasattr(settings, 'LSH_JACCARD_THRESHOLD') else 0.8
LSH_INDEX_FILE = "storage/metadata/lsh_index.pkl"

# Ensure metadata directory exists for LSH index
os.makedirs(os.path.dirname(LSH_INDEX_FILE), exist_ok=True)


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
    Create an empty Locality-Sensitive Hashing (LSH) index.
    
    Args:
        threshold: Jaccard similarity threshold
        num_perm: Number of permutations for MinHash
        
    Returns:
        An empty LSH index
    """
    return MinHashLSH(threshold=threshold, num_perm=num_perm)


def rebuild_lsh_index_from_db(lsh_index: MinHashLSH, db: Session) -> None:
    """
    Populates the LSH index with MinHash signatures from the database.
    This should be called to initialize or update an in-memory LSH index.

    Args:
        lsh_index: An existing MinHashLSH index object to populate.
        db: SQLAlchemy session.
    """
    logger.info("Rebuilding LSH index from database...")
    count = 0
    try:
        for doc_meta in db.query(DocumentMetadata.doc_id, DocumentMetadata.minhash_signature).filter(DocumentMetadata.minhash_signature.isnot(None)).all():
            doc_id, minhash_bytes = doc_meta
            if minhash_bytes:
                try:
                    minhash_obj = MinHash.deserialize(minhash_bytes)
                    lsh_index.insert(doc_id, minhash_obj)
                    count += 1
                except Exception as e: # More specific exceptions can be caught if needed
                    logger.error(f"Error deserializing or inserting MinHash for doc_id {doc_id}: {e}")
        logger.info(f"LSH index rebuilt with {count} entries from database.")
    except Exception as e:
        logger.error(f"Error querying MinHash signatures from database: {e}", exc_info=True)


def get_lsh_index_instance() -> MinHashLSH:
    """
    Loads the LSH index from disk. 
    If the file doesn't exist, returns a new, empty LSH index and logs a warning.
    The periodic Celery task is responsible for creating and populating the index file.
    """
    if os.path.exists(LSH_INDEX_FILE):
        try:
            with open(LSH_INDEX_FILE, 'rb') as f:
                logger.info(f"Loading LSH index from {LSH_INDEX_FILE}")
                return pickle.load(f)
        except Exception as e:
            logger.error(f"Error loading LSH index from {LSH_INDEX_FILE}: {e}. Returning an empty index.")
            # Fall through to returning a new, empty index
    else:
        logger.warning(f"LSH index file not found at {LSH_INDEX_FILE}. Returning an empty index. The rebuild task should create this file.")
    
    # Return a new, empty LSH index if loading failed or file not found
    return create_lsh_index(threshold=JACCARD_THRESHOLD, num_perm=NUM_PERM)


def save_lsh_index_instance(lsh_index: MinHashLSH) -> None:
    """
    Saves the given LSH index to disk using a temporary file for atomic-like operation.
    """
    temp_file_path = LSH_INDEX_FILE + ".tmp"
    try:
        with open(temp_file_path, 'wb') as f_temp:
            pickle.dump(lsh_index, f_temp)
        os.rename(temp_file_path, LSH_INDEX_FILE) # Atomic on POSIX if src and dest are on the same filesystem
        logger.info(f"LSH index saved to {LSH_INDEX_FILE}")
    except Exception as e:
        logger.error(f"Error saving LSH index to {LSH_INDEX_FILE}: {e}", exc_info=True)
        # Attempt to clean up temp file if an error occurred
        if os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
                logger.info(f"Removed temporary LSH index file: {temp_file_path}")
            except OSError as rm_err:
                logger.error(f"Error removing temporary LSH index file {temp_file_path}: {rm_err}")


def query_lsh_index(lsh_index: MinHashLSH, minhash: MinHash) -> List[str]:
    """
    Query the in-memory LSH index for similar documents.
    
    Args:
        lsh_index: LSH index
        minhash: MinHash object for the query
        
    Returns:
        List of similar document IDs
    """
    # Lock removed, operates on in-memory index.
    if minhash:
        return lsh_index.query(minhash)
    else:
        logger.warning("Attempted to query LSH index with None MinHash. Returning empty list.")
        return []


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
        minhash_obj = get_minhash(text)
        serialized_minhash = minhash_obj.leanbytes() if minhash_obj else None
        
        return {
            "hash": doc_hash,
            "page_hashes": page_hashes,
            "minhash": serialized_minhash,
            "num_pages": len(pages)
        }
    except Exception as e:
        logger.error(f"Error creating document fingerprint: {e}")
        return {"error": str(e)}