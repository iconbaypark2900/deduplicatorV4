"""
Page tracking utility for managing page hashes and document relationships.
Provides functions for hash generation, storage, and retrieval.
"""

import hashlib
import json
import os
from typing import List, Dict, Optional, Any
import logging

# Configure logging
logger = logging.getLogger(__name__)

# Path to page hash map
PAGE_HASH_MAP_PATH = "storage/metadata/page_hash_map.json"


def hash_text(text: str) -> str:
    """
    Hash the normalized text content of a page using SHA256.
    
    Args:
        text: Text to hash
        
    Returns:
        SHA256 hash of the text
    """
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


def ensure_storage_exists() -> None:
    """
    Ensure the storage directory and files exist.
    """
    os.makedirs(os.path.dirname(PAGE_HASH_MAP_PATH), exist_ok=True)
    if not os.path.exists(PAGE_HASH_MAP_PATH):
        with open(PAGE_HASH_MAP_PATH, 'w') as f:
            json.dump({}, f)
            logger.info(f"Created new page hash map at {PAGE_HASH_MAP_PATH}")


def load_page_hash_map() -> Dict:
    """
    Load the page hash map, creating it if it doesn't exist.
    
    Returns:
        Dictionary mapping page hashes to page metadata
    """
    ensure_storage_exists()
    with open(PAGE_HASH_MAP_PATH, 'r') as f:
        try:
            page_map = json.load(f)
            logger.debug(f"Loaded page hash map with {len(page_map)} entries")
            return page_map
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON in {PAGE_HASH_MAP_PATH}, returning empty map")
            return {}


def save_page_hash_map(page_map: Dict) -> None:
    """
    Save the page hash map to disk.
    
    Args:
        page_map: Dictionary mapping page hashes to page metadata
    """
    os.makedirs(os.path.dirname(PAGE_HASH_MAP_PATH), exist_ok=True)
    with open(PAGE_HASH_MAP_PATH, "w") as f:
        json.dump(page_map, f, indent=2)
        logger.debug(f"Saved page hash map with {len(page_map)} entries")


def update_page_hash_map(
    doc_id: str,
    filename: str,
    page_texts: List[str],
    medical_confidences: Optional[List[float]] = None,
    duplicate_confidences: Optional[List[float]] = None,
    image_paths: Optional[List[str]] = None
) -> List[str]:
    """
    Update the page hash map with new page data.
    
    Args:
        doc_id: Document identifier
        filename: Original filename
        page_texts: List of page texts
        medical_confidences: List of medical confidence scores
        duplicate_confidences: List of duplicate confidence scores
        image_paths: List of paths to page images
        
    Returns:
        List of page hashes
    """
    page_map = load_page_hash_map()
    page_hashes = []
    
    # Prepare confidence lists if not provided
    if medical_confidences is None:
        medical_confidences = [0.0] * len(page_texts)
    if duplicate_confidences is None:
        duplicate_confidences = [0.0] * len(page_texts)
    if image_paths is None:
        image_paths = [None] * len(page_texts)
    
    # Ensure lists are the same length
    if len(medical_confidences) != len(page_texts):
        logger.warning(f"Length mismatch: {len(medical_confidences)} medical_confidences vs {len(page_texts)} texts")
        medical_confidences = medical_confidences[:len(page_texts)] + [0.0] * (len(page_texts) - len(medical_confidences))
        
    if len(duplicate_confidences) != len(page_texts):
        logger.warning(f"Length mismatch: {len(duplicate_confidences)} duplicate_confidences vs {len(page_texts)} texts")
        duplicate_confidences = duplicate_confidences[:len(page_texts)] + [0.0] * (len(page_texts) - len(duplicate_confidences))
        
    if len(image_paths) != len(page_texts):
        logger.warning(f"Length mismatch: {len(image_paths)} image_paths vs {len(page_texts)} texts")
        image_paths = image_paths[:len(page_texts)] + [None] * (len(page_texts) - len(image_paths))
    
    for i, text in enumerate(page_texts, start=1):
        if not text.strip():
            logger.warning(f"Empty text for page {i} of {filename}, skipping")
            continue
            
        page_hash = hash_text(text)
        page_hashes.append(page_hash)
        
        # Check if this page hash already exists
        existing_entry = page_map.get(page_hash)
        
        if existing_entry:
            # Update the duplicate references
            source_doc = existing_entry.get('source_doc', '')
            page_num = existing_entry.get('page_num', 0)
            
            # Don't reference itself as a duplicate
            if source_doc != filename or page_num != i:
                duplicates = existing_entry.get('duplicates', [])
                
                # Add this document as a duplicate if not already present
                dup_entry = {
                    "doc_id": doc_id,
                    "filename": filename,
                    "page_num": i
                }
                
                # Check if this exact duplicate entry already exists
                if not any(
                    d.get('doc_id') == doc_id and 
                    d.get('filename') == filename and 
                    d.get('page_num') == i
                    for d in duplicates
                ):
                    duplicates.append(dup_entry)
                    existing_entry['duplicates'] = duplicates
                    page_map[page_hash] = existing_entry
                    logger.info(f"Added {filename} page {i} as duplicate to existing page {page_hash}")
        else:
            # Create new entry
            page_map[page_hash] = {
                "source_doc": filename,
                "doc_id": doc_id,
                "page_num": i,
                "text_snippet": text[:300].replace("\n", " ").strip(),
                "duplicates": [],
                "decision": "unreviewed",
                "medical_confidence": medical_confidences[i-1],
                "duplicate_confidence": duplicate_confidences[i-1],
                "image_path": image_paths[i-1]
            }
            logger.info(f"Added new page hash {page_hash} for {filename} page {i}")
    
    # Debug logging
    logger.debug(f"Saving {len(page_texts)} pages for doc_id {doc_id}")
    logger.debug(f"Page hashes: {page_hashes}")
    
    save_page_hash_map(page_map)
    return page_hashes


def get_page_metadata(page_hash: str) -> Optional[Dict[str, Any]]:
    """
    Get metadata for a specific page hash.
    
    Args:
        page_hash: Page hash to look up
        
    Returns:
        Dictionary with page metadata, or None if not found
    """
    page_map = load_page_hash_map()
    return page_map.get(page_hash)


def update_page_status(page_hash: str, status: str, reviewer: str, notes: Optional[str] = None) -> bool:
    """
    Update the status of a page.
    
    Args:
        page_hash: Page hash to update
        status: New status ("unique", "duplicate", etc.)
        reviewer: Identifier of the reviewer
        notes: Optional notes about the decision
        
    Returns:
        True if update was successful, False otherwise
    """
    page_map = load_page_hash_map()
    
    if page_hash not in page_map:
        logger.warning(f"Page hash {page_hash} not found in map")
        return False
    
    page_entry = page_map[page_hash]
    page_entry["decision"] = status
    page_entry["reviewed_by"] = reviewer
    
    if notes:
        page_entry["review_notes"] = notes
    
    import datetime
    page_entry["reviewed_at"] = datetime.datetime.utcnow().isoformat()
    
    page_map[page_hash] = page_entry
    save_page_hash_map(page_map)
    logger.info(f"Updated status of {page_hash} to {status} by {reviewer}")
    return True


def find_duplicates_of_page(page_hash: str) -> List[Dict[str, Any]]:
    """
    Find all duplicates of a specific page.
    
    Args:
        page_hash: Page hash to find duplicates for
        
    Returns:
        List of dictionaries with duplicate page information
    """
    page_map = load_page_hash_map()
    
    if page_hash not in page_map:
        logger.warning(f"Page hash {page_hash} not found in map")
        return []
    
    return page_map[page_hash].get("duplicates", [])


def search_page_snippets(query: str, max_results: int = 10) -> List[Dict[str, Any]]:
    """
    Search for pages containing the query in their text snippet.
    
    Args:
        query: Search query
        max_results: Maximum number of results to return
        
    Returns:
        List of dictionaries with matching page information
    """
    page_map = load_page_hash_map()
    results = []
    
    query = query.lower()
    
    for page_hash, page_data in page_map.items():
        snippet = page_data.get("text_snippet", "").lower()
        
        if query in snippet:
            results.append({
                "page_hash": page_hash,
                "doc_id": page_data.get("doc_id"),
                "filename": page_data.get("source_doc"),
                "page_num": page_data.get("page_num"),
                "text_snippet": page_data.get("text_snippet"),
                "decision": page_data.get("decision", "unreviewed")
            })
            
            if len(results) >= max_results:
                break
                
    return results


def get_pages_by_doc_id(doc_id: str) -> List[Dict[str, Any]]:
    """
    Get all pages for a specific document.
    
    Args:
        doc_id: Document identifier to find pages for
        
    Returns:
        List of dictionaries with page information
    """
    page_map = load_page_hash_map()
    results = []
    
    for page_hash, page_data in page_map.items():
        if page_data.get("doc_id") == doc_id:
            results.append({
                "page_hash": page_hash,
                "page_num": page_data.get("page_num"),
                "text_snippet": page_data.get("text_snippet"),
                "decision": page_data.get("decision", "unreviewed"),
                "medical_confidence": page_data.get("medical_confidence", 0.0),
                "duplicate_confidence": page_data.get("duplicate_confidence", 0.0),
                "image_path": page_data.get("image_path")
            })
    
    # Sort by page number
    results.sort(key=lambda x: x.get("page_num", 0))
    return results