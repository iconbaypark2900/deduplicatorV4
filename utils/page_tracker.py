"""
Page tracking utility for managing page hashes and document relationships.
Provides functions for hash generation and database interaction for page data.
"""

import hashlib
import logging
from typing import List, Optional, Any, Dict # Added Dict
import datetime # Added for reviewed_at timestamp

from sqlalchemy.orm import Session

# Import database functions and models
from utils.database import (
    Page,
    # User, # Not directly used here, but get_user_by_username returns it
    create_page,
    get_page_by_hash,
    create_page_duplicate,
    get_duplicates_for_page, # Renamed from get_duplicates_of_page for clarity
    create_page_review_decision,
    get_user_by_username,
    search_pages_by_snippet,
    get_pages_by_document_id as db_get_pages_by_document_id # Alias to avoid name clash
)

# Configure logging
logger = logging.getLogger(__name__)


def hash_text(text: str) -> str:
    """
    Hash the normalized text content of a page using SHA256.
    
    Args:
        text: Text to hash
        
    Returns:
        SHA256 hash of the text
    """
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


def process_document_pages( # Renamed from update_page_hash_map for clarity and new role
    db: Session,
    doc_id: str,
    # filename: str, # Filename is part of DocumentMetadata, not directly needed here if doc_id is key
    page_texts: List[str],
    medical_confidences: Optional[List[float]] = None,
    duplicate_confidences: Optional[List[float]] = None,
    image_paths: Optional[List[str]] = None
) -> List[Page]: # Returns list of created/updated Page objects
    """
    Processes pages for a document, creates Page records in the database,
    and handles duplicate page detection by hash.
    
    Args:
        db: SQLAlchemy session
        doc_id: Document identifier (links to DocumentMetadata)
        page_texts: List of page texts
        medical_confidences: List of medical confidence scores
        duplicate_confidences: List of duplicate confidence scores
        image_paths: List of paths to page images
        
    Returns:
        List of created Page objects.
    """
    created_pages: List[Page] = []
    
    # Prepare confidence lists if not provided
    num_pages = len(page_texts)
    medical_confidences = medical_confidences or [0.0] * num_pages
    duplicate_confidences = duplicate_confidences or [0.0] * num_pages
    image_paths = image_paths or [None] * num_pages # type: ignore
    
    # Ensure lists are the same length as page_texts
    # This logic can be simplified or made more robust if necessary
    if not (len(medical_confidences) == num_pages and \
            len(duplicate_confidences) == num_pages and \
            len(image_paths) == num_pages):
        logger.warning(f"Mismatch in lengths of page data for doc_id {doc_id}. Adjusting lists.")
        # Basic adjustment, consider more robust error handling or raising an exception
        medical_confidences = (medical_confidences + [0.0] * num_pages)[:num_pages]
        duplicate_confidences = (duplicate_confidences + [0.0] * num_pages)[:num_pages]
        image_paths = (image_paths + [None] * num_pages)[:num_pages] # type: ignore

    for i, text in enumerate(page_texts, start=1): # page_number is 1-indexed
        page_num = i
        if not text.strip():
            logger.warning(f"Empty text for page {page_num} of doc_id {doc_id}, skipping")
            continue
            
        page_hash_val = hash_text(text)
        
        # Check if this page hash already exists
        existing_page_with_hash = get_page_by_hash(db, page_hash_val)
        
        # Create the new page entry regardless
        # The relationship will be handled by PageDuplicate
        current_page = create_page(
            db=db,
            document_id=doc_id,
            page_number=page_num,
            page_hash=page_hash_val,
            text_snippet=text[:300].replace("\n", " ").strip(),
            medical_confidence=medical_confidences[page_num-1],
            duplicate_confidence=duplicate_confidences[page_num-1],
            page_image_path=image_paths[page_num-1], # type: ignore
            status="pending" # Default status
        )
        created_pages.append(current_page)
        # db.flush() # Ensure current_page.id is available if not using autocommit for create_page

        if existing_page_with_hash:
            # If the existing page is not the one we just created (i.e. different ID)
            # This check is important if reprocessing the same document.
            if existing_page_with_hash.id != current_page.id:
                # Check if this exact duplicate relationship already exists to prevent errors
                # This might require a specific query if unique constraint is on (source_page_id, duplicate_page_id)
                # For now, we assume create_page_duplicate handles or ignores duplicates gracefully
                # or the calling logic ensures no redundant calls.
                # The PageDuplicate table has a unique constraint on (source_page_id, duplicate_page_id)
                # So, attempting to add an existing one might raise an IntegrityError.
                # A check could be added here if needed:
                # existing_dup = db.query(PageDuplicate).filter_by(source_page_id=existing_page_with_hash.id, duplicate_page_id=current_page.id).first()
                # if not existing_dup:

                create_page_duplicate(
                    db=db,
                    source_page_id=existing_page_with_hash.id, # The first page encountered with this hash
                    duplicate_page_id=current_page.id,        # The new page that is a duplicate
                    similarity=1.0  # Exact hash match
                )
                logger.info(f"Page {current_page.id} (doc: {doc_id}, page_num: {page_num}) identified as duplicate of page {existing_page_with_hash.id} (hash: {page_hash_val})")
            else:
                logger.info(f"Page {current_page.id} (doc: {doc_id}, page_num: {page_num}) with hash {page_hash_val} is the same as the existing entry, likely a re-process.")

        else:
            logger.info(f"Added new unique page {current_page.id} (doc: {doc_id}, page_num: {page_num}) with hash {page_hash_val}")
            
    logger.info(f"Processed {len(created_pages)} pages for doc_id {doc_id}.")
    return created_pages


def get_page_info_by_hash(db: Session, page_hash: str) -> Optional[Page]:
    """
    Get Page object for a specific page hash.
    This replaces the old get_page_metadata.
    
    Args:
        db: SQLAlchemy session
        page_hash: Page hash to look up
        
    Returns:
        Page object or None if not found
    """
    return get_page_by_hash(db, page_hash)


def update_page_review_status(
    db: Session, 
    page_hash: str, 
    decision: str, 
    reviewer_username: str, 
    notes: Optional[str] = None,
    reviewed_at: Optional[datetime.datetime] = None # Added for consistency
) -> bool:
    """
    Update the review status of a page by creating a PageReviewDecision.
    The Page.status field is also updated by create_page_review_decision.
    
    Args:
        db: SQLAlchemy session
        page_hash: Page hash to update
        decision: New status/decision (e.g., "unique", "duplicate_kept", "to_archive")
        reviewer_username: Username of the reviewer
        notes: Optional notes about the decision
        reviewed_at: Optional timestamp for the review
        
    Returns:
        True if update was successful, False otherwise
    """
    page_to_review = get_page_by_hash(db, page_hash)
    if not page_to_review:
        logger.warning(f"Page hash {page_hash} not found. Cannot update status.")
        return False
    
    reviewer = get_user_by_username(db, reviewer_username)
    if not reviewer:
        logger.warning(f"Reviewer username {reviewer_username} not found. Cannot update page status for {page_hash}.")
        # Optionally, create a placeholder user or assign to a default system user,
        # or simply disallow if reviewer not found. For now, fail.
        return False

    try:
        create_page_review_decision(
            db=db,
            page_id=page_to_review.id,
            user_id=reviewer.id,
            decision=decision,
            notes=notes,
            reviewed_at=reviewed_at # Pass through the optional timestamp
        )
        # The Page.status is updated within create_page_review_decision
        logger.info(f"Successfully created review decision for page {page_to_review.id} (hash: {page_hash}) with status {decision} by {reviewer_username}")
        return True
    except Exception as e:
        logger.error(f"Error creating page review decision for page {page_to_review.id} (hash: {page_hash}): {e}", exc_info=True)
        return False


def find_page_duplicates(db: Session, page_hash: str) -> List[Page]:
    """
    Find all Page objects that are duplicates of the page identified by page_hash.
    The identified page is considered the "source" or "original" in this context.
    
    Args:
        db: SQLAlchemy session
        page_hash: Page hash to find duplicates for
        
    Returns:
        List of Page objects that are duplicates of the given page.
    """
    source_page = get_page_by_hash(db, page_hash)
    if not source_page:
        logger.warning(f"Source page with hash {page_hash} not found. Cannot find duplicates.")
        return []
    
    # get_duplicates_for_page expects source_page_id
    return get_duplicates_for_page(db, source_page.id)

# For API consistency if needed, or direct use of database.search_pages_by_snippet
def search_page_text_snippets(db: Session, query: str, max_results: int = 10) -> List[Page]:
    """
    Search pages by text snippet.
    
    Args:
        db: SQLAlchemy session
        query: Text to search for in snippets
        max_results: Maximum number of results to return
        
    Returns:
        List of Page objects matching the query.
    """
    return search_pages_by_snippet(db, query, max_results)

# This function can now be directly replaced by utils.database.get_pages_by_document_id
# but we can keep it as a pass-through for interface consistency if other modules use it from here.
def get_all_pages_for_document(db: Session, doc_id: str) -> List[Page]:
    """
    Get all Page objects associated with a specific document ID.
    
    Args:
        db: SQLAlchemy session
        doc_id: Document identifier
        
    Returns:
        List of Page objects for that document.
    """
    return db_get_pages_by_document_id(db, doc_id)

# Deprecated JSON-based functions:
# ensure_storage_exists - REMOVED
# load_page_hash_map - REMOVED
# save_page_hash_map - REMOVED

# Potentially other helper functions if any were purely for JSON manipulation.