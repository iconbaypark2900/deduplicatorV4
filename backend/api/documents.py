"""
Document-level API endpoints.
Provides routes for retrieving and manipulating documents.
"""

import os
# import json # REMOVED
import logging
import shutil # ADDED for file operations
from fastapi import APIRouter, HTTPException, Query, Path, Body, Depends # MODIFIED: Added Depends
from fastapi.responses import FileResponse, JSONResponse # JSONResponse (already imported)
from typing import List, Dict, Optional, Any
from datetime import datetime

# MODIFIED: Added PageInfo for DocumentAnalysis.pages type hint
from backend.models.schemas import DocumentAnalysis, DocumentStatusUpdate, RebuildRequest, PageInfo, DuplicatePair, ReviewHistoryEntry, ReviewStatus
# MODIFIED: Updated page_tracker import
from utils.page_tracker import get_all_pages_for_document, get_page_info_by_hash
# from backend.services.rebuilder import rebuild_from_unique_pages, merge_documents # merge_documents not used, rebuild_from_unique_pages is different from rebuild_document
from backend.services.rebuilder import rebuild_document as service_rebuild_document # Aliased to avoid conflict
from utils.config import settings

# ADDED: Database imports
from sqlalchemy.orm import Session
from utils.database import (
    get_db,
    DocumentMetadata,
    Page, # For type hinting if needed
    PageDuplicate, # For querying within-document duplicates
    ReviewHistory,
    User,
    get_document_metadata_by_id,
    create_review_history_entry,
    get_review_history_for_document,
    get_user_by_username,
    get_recent_document_metadata, # Added this function
    upsert_document_metadata # For updating file_path and status
)


# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/documents", tags=["Documents"])

# REMOVED: File paths
# DOCUMENT_METADATA_PATH = "storage/metadata/document_metadata.json"


# Helper function to get intra-document page duplicates
def _get_intra_document_page_duplicates(db: Session, doc_id: str) -> List[DuplicatePair]:
    """
    Finds pairs of pages within the same document that are duplicates of each other.
    """
    # Get all pages for the document
    pages_in_doc = db.query(Page.id, Page.page_number).filter(Page.document_id == doc_id).all()
    page_id_to_num_map = {pid: pnum for pid, pnum in pages_in_doc}
    page_ids_in_doc = list(page_id_to_num_map.keys())

    if not page_ids_in_doc or len(page_ids_in_doc) < 2:
        return []

    # Find PageDuplicate entries where both source and duplicate page IDs are within this document
    # and source_page_id < duplicate_page_id to avoid listing (B,A) if (A,B) is already found.
    # This assumes similarity is 1.0 for hash-based duplicates.
    duplicate_relations = db.query(PageDuplicate).\
        filter(
            PageDuplicate.source_page_id.in_(page_ids_in_doc),
            PageDuplicate.duplicate_page_id.in_(page_ids_in_doc),
            PageDuplicate.source_page_id < PageDuplicate.duplicate_page_id # Avoid duplicates and self-references
        ).\
        all()

    duplicate_pairs: List[DuplicatePair] = []
    for rel in duplicate_relations:
        # Ensure both pages are indeed part of the current document,
        # (already filtered by .in_() but good for clarity)
        # and map IDs back to 0-indexed page numbers for DuplicatePair model if it expects that
        # The PageInfo model uses 'index' which might be 0-based.
        # Page.page_number is 1-based. Let's assume DuplicatePair page indices are 0-based for now.
        source_page_num = page_id_to_num_map.get(rel.source_page_id)
        duplicate_page_num = page_id_to_num_map.get(rel.duplicate_page_id)

        if source_page_num is not None and duplicate_page_num is not None:
            duplicate_pairs.append(
                DuplicatePair(
                    page1_idx=source_page_num -1, # Assuming 0-indexed for schema
                    page2_idx=duplicate_page_num -1, # Assuming 0-indexed for schema
                    similarity=rel.similarity
                )
            )
    return duplicate_pairs


@router.get("/{doc_id}/analysis", response_model=DocumentAnalysis)
async def get_document_analysis(doc_id: str, db: Session = Depends(get_db)): # MODIFIED: Added db session
    """
    Get detailed analysis for a document.
    
    Args:
        doc_id: Document identifier
        
    Returns:
        Document analysis data
        
    Raises:
        HTTPException: If document is not found
    """
    try:
        doc_meta = get_document_metadata_by_id(db, doc_id)
        if not doc_meta:
            raise HTTPException(status_code=404, detail=f"Document with ID {doc_id} not found")

        # Get pages from page_tracker (which now uses DB)
        page_objects = get_all_pages_for_document(db, doc_id) # Returns List[Page]
        
        pages_info: List[PageInfo] = []
        for p_obj in page_objects:
            pages_info.append(PageInfo(
                hash=p_obj.page_hash,
                index=p_obj.page_number -1, # Assuming PageInfo.index is 0-based
                text_snippet=p_obj.text_snippet or "",
                medical_confidence=p_obj.medical_confidence,
                duplicate_confidence=p_obj.duplicate_confidence
            ))
        
        # Get review history
        review_history_entries_db = get_review_history_for_document(db, doc_id)
        review_history_api: List[ReviewHistoryEntry] = []
        last_reviewer: Optional[str] = None
        last_reviewed_at: Optional[str] = None

        if review_history_entries_db:
            # Sort by timestamp descending to get the latest review first for lastReviewer/lastReviewedAt
            review_history_entries_db.sort(key=lambda x: x.review_timestamp, reverse=True)
            latest_review = review_history_entries_db[0]
            if latest_review.user:
                last_reviewer = latest_review.user.username
            else: # E.g. if user_id was null for some system action
                 last_reviewer = "System" 
            last_reviewed_at = latest_review.review_timestamp.isoformat()

            for entry in review_history_entries_db:
                review_history_api.append(ReviewHistoryEntry(
                    reviewer=entry.user.username if entry.user else "System",
                    timestamp=entry.review_timestamp.isoformat(),
                    action=entry.action,
                    notes=entry.notes
                ))
        
        # Create response
        return {
            "doc_id": doc_id,
            "filename": doc_meta.filename,
            "status": doc_meta.status,
            "pages": pages_info,
            "duplicates": _get_intra_document_page_duplicates(db, doc_id),
            "lastReviewer": last_reviewer,
            "lastReviewedAt": last_reviewed_at,
            "reviewHistory": review_history_api
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving document analysis: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error retrieving document analysis: {str(e)}")


@router.post("/{doc_id}/status")
async def update_document_status(doc_id: str, status_update: DocumentStatusUpdate, db: Session = Depends(get_db)):
    """
    Update the status of a document and its file path after moving.
    Records the action in the review history.
    
    Args:
        doc_id: Document identifier from path.
        status_update: Status update data including action, reviewer, and notes.
        db: Database session.
        
    Returns:
        Success message.
        
    Raises:
        HTTPException: If document is not found or update fails.
    """
    try:
        logger.debug(f"Updating status for doc_id: {doc_id} to {status_update.action}")
        doc_meta = get_document_metadata_by_id(db, doc_id)
        if not doc_meta:
            raise HTTPException(status_code=404, detail=f"Document with ID {doc_id} not found")

        # Determine source path from metadata or fall back to original filename if path not set
        # This assumes doc_meta.filename is the original uploaded name, and initial file_path might be in a default location.
        source_filename = doc_meta.filename # Original filename
        if not doc_meta.file_path or not os.path.exists(doc_meta.file_path):
            logger.warning(f"doc_meta.file_path for {doc_id} is not set or does not exist: '{doc_meta.file_path}'. Attempting to find file in common locations.")
            # Fallback logic to find the file - this should ideally be unnecessary if file_path is always correct
            potential_source_subdirs = [
                settings.UNIQUE_DOCS_SUBPATH, 
                settings.ARCHIVED_DOCS_SUBPATH, 
                settings.FLAGGED_DOCS_SUBPATH,
                "" # Check directly in DOCUMENT_PATH as well (e.g. initial upload location)
            ]
            found_source_path = None
            for subdir in potential_source_subdirs:
                # Assuming doc_id can serve as filename if original filename is missing extension, or use doc_meta.filename
                # For robustness, we should use doc_meta.filename which should include the extension.
                # If doc_id is used as filename, ensure it includes .pdf or handle dynamically.
                # For now, let's assume the filename to look for is based on doc_id.pdf or original filename.
                # The old code used f"{doc_id}.pdf", let's stick to that pattern for finding.
                current_try_path = os.path.join(settings.DOCUMENT_PATH, subdir, f"{doc_id}.pdf") 
                if os.path.exists(current_try_path):
                    found_source_path = current_try_path
                    logger.info(f"Found source file at: {found_source_path}")
                    break
            
            if not found_source_path:
                 # If original filename might be different than doc_id.pdf
                for subdir in potential_source_subdirs:
                    current_try_path = os.path.join(settings.DOCUMENT_PATH, subdir, source_filename)
                    if os.path.exists(current_try_path):
                        found_source_path = current_try_path
                        logger.info(f"Found source file (using original_filename) at: {found_source_path}")
                        break

            if not found_source_path:
                logger.error(f"Source file for doc_id {doc_id} (filename: {source_filename}) not found after checking multiple paths.")
                raise HTTPException(status_code=404, detail=f"Source file for document {doc_id} not found. Cannot update status.")
            source_path = found_source_path
            # Optionally update doc_meta.file_path here if it was missing and now found
            if not doc_meta.file_path:
                doc_meta.file_path = source_path # Keep track of where it was found before move
        else:
            source_path = doc_meta.file_path
            logger.info(f"Using source file path from metadata: {source_path}")

        # Determine destination path based on action
        dest_subpath = ""
        new_status_str = ""

        if status_update.action == ReviewStatus.KEEP:
            dest_subpath = settings.UNIQUE_DOCS_SUBPATH
            new_status_str = "unique" # Status in DB
        elif status_update.action == ReviewStatus.ARCHIVE:
            dest_subpath = settings.ARCHIVED_DOCS_SUBPATH
            new_status_str = "archived"
        elif status_update.action == ReviewStatus.PENDING:
            dest_subpath = settings.FLAGGED_DOCS_SUBPATH
            new_status_str = "pending_review" # Or just "pending"
        else:
            raise HTTPException(status_code=400, detail=f"Invalid action: {status_update.action}")

        # Ensure the actual filename (with extension) from the source_path is used for the destination.
        actual_filename = os.path.basename(source_path)
        dest_path = os.path.join(settings.DOCUMENT_PATH, dest_subpath, actual_filename)
        
        # Create destination directory if it doesn't exist
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)

        # Move the file only if the path changes
        if source_path != dest_path:
            logger.info(f"Moving file from {source_path} to {dest_path}")
            shutil.move(source_path, dest_path) # Using move, or copy then delete old one
            # If using copy: shutil.copy2(source_path, dest_path)
            # And then: os.remove(source_path) if you want to ensure original is gone
            doc_meta.file_path = dest_path # Update to the new path
        else:
            logger.info(f"File {actual_filename} is already in the correct location: {dest_path}")
            # Ensure file_path is set even if no move occurs, if it was missing.
            if not doc_meta.file_path:
                 doc_meta.file_path = source_path

        # Update document status in DB
        doc_meta.status = new_status_str
        
        # Record review history
        user_id_for_history = None
        if status_update.reviewer:
            user = get_user_by_username(db, status_update.reviewer)
            if user:
                user_id_for_history = user.id
            else:
                logger.warning(f"Reviewer username '{status_update.reviewer}' not found. Storing review history without user_id.")
        
        # The 'action' in ReviewHistoryEntry schema was used for 'status_update.action' from JSON before.
        # Let's map ReviewStatus enum to a string for the history's 'action' or 'decision' field.
        # The ReviewHistory table has 'decision' and 'notes'. Let's use status_update.action for 'decision'.
        create_review_history_entry(
            db=db, 
            document_id=doc_id, 
            user_id=user_id_for_history, 
            # The ReviewHistory table in database.py has 'decision', not 'action'. 
            # Let's use status_update.action.value for the decision field.
            decision=status_update.action.value, 
            notes=status_update.notes
        )
        
        db.commit()
        db.refresh(doc_meta)
        
        logger.info(f"Document {doc_id} status updated to '{new_status_str}', file_path to '{doc_meta.file_path}'. Review by {status_update.reviewer or 'N/A'}.")
        return {"message": f"Document {doc_id} status updated to {status_update.action.value}, file path updated to {doc_meta.file_path}"}

    except HTTPException as http_exc:
        logger.error(f"HTTPException in update_document_status for {doc_id}: {http_exc.detail}")
        db.rollback() # Rollback on HTTPException if it's a validation or setup error before commit
        raise
    except Exception as e:
        logger.error(f"Error updating document status for {doc_id}: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error updating document status: {str(e)}")


@router.post("/rebuild")
async def rebuild_document(rebuild_request: RebuildRequest, db: Session = Depends(get_db)): # Added db session
    """
    Rebuild a document from selected pages.
    
    Args:
        rebuild_request: Rebuild request data
        db: Database session
        
    Returns:
        Path to the rebuilt document
        
    Raises:
        HTTPException: If rebuild fails
    """
    try:
        # Generate output path
        output_filename = f"rebuilt_{rebuild_request.filename}"
        output_path = os.path.join(settings.TEMP_PATH, output_filename)
        
        page_selections = []
        if not rebuild_request.pages:
            raise HTTPException(status_code=400, detail="No pages selected for rebuild.")

        for page_hash in rebuild_request.pages:
            # Get Page object using the hash
            page_obj = get_page_info_by_hash(db, page_hash) # from utils.page_tracker, returns Page or None
            
            if not page_obj:
                logger.warning(f"Page with hash {page_hash} not found in database. Skipping.")
                continue
                
            doc_id = page_obj.document_id
            page_num_in_db = page_obj.page_number # This is 1-based

            if not doc_id: # Should not happen if page_obj is valid
                logger.warning(f"Page with hash {page_hash} has no document_id. Skipping.")
                continue
            
            # Get DocumentMetadata to find the source file path
            doc_meta = get_document_metadata_by_id(db, doc_id)
            if not doc_meta:
                logger.warning(f"DocumentMetadata for doc_id {doc_id} (from page hash {page_hash}) not found. Skipping page.")
                continue

            source_path = doc_meta.file_path
            if not source_path or not os.path.exists(source_path):
                logger.warning(f"Source file path '{source_path}' for doc_id {doc_id} (page hash {page_hash}) not found or is invalid. Skipping page.")
                # Attempt to reconstruct path as a fallback - useful during transition
                # This fallback can be removed once file_path is reliably populated everywhere.
                logger.info(f"Attempting fallback to locate file for doc_id {doc_id}")
                potential_source_subdirs = [
                    settings.UNIQUE_DOCS_SUBPATH, 
                    settings.ARCHIVED_DOCS_SUBPATH, 
                    settings.FLAGGED_DOCS_SUBPATH,
                    "" # Check directly in DOCUMENT_PATH
                ]
                found_fallback_path = None
                # The filename for documents in storage is expected to be {doc_id}.pdf or original_filename
                # Let's assume it's {doc_id}.pdf as pipeline_orchestrator now saves it this way.
                filename_to_check = f"{doc_id}.pdf" 
                
                for subdir in potential_source_subdirs:
                    current_try_path = os.path.join(settings.DOCUMENT_PATH, subdir, filename_to_check)
                    if os.path.exists(current_try_path):
                        found_fallback_path = current_try_path
                        logger.info(f"Fallback: Found source file for doc_id {doc_id} at: {found_fallback_path}")
                        break
                
                if found_fallback_path:
                    source_path = found_fallback_path
                    # Optionally, update doc_meta.file_path here if it was missing/wrong and found via fallback
                    # doc_meta.file_path = source_path 
                    # db.commit() # If we decide to self-correct
                else:
                    logger.warning(f"Fallback failed: Source PDF for doc_id {doc_id} not found in standard locations. Skipping page hash {page_hash}.")
                    continue
            
            page_selections.append({
                "source_path": source_path,
                "page_number": page_num_in_db - 1,  # Convert 1-based from DB to 0-based for rebuilder service
                "doc_id": doc_id
            })
        
        if not page_selections:
            logger.error("No valid pages could be prepared for document rebuild.")
            raise HTTPException(status_code=400, detail="Could not find source data for any of the selected pages.")

        # Rebuild document (this function name was aliased at import)
        result_path = service_rebuild_document(output_path, page_selections) 
        
        logger.info(f"Document rebuilt successfully: {output_filename} at {result_path}")
        return {"path": result_path, "filename": output_filename}
        
    except HTTPException as http_exc:
        logger.error(f"HTTPException during document rebuild: {http_exc.detail}", exc_info=True)
        raise # Re-raise HTTPException
    except Exception as e:
        logger.error(f"Error rebuilding document: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error rebuilding document: {str(e)}")


@router.get("/recent", response_model=List[Dict[str, Any]])
async def get_recent_documents(limit: int = 10, db: Session = Depends(get_db)):
    """
    Get the most recently uploaded documents from the database.
    
    Args:
        limit: Maximum number of documents to return.
        db: Database session.
        
    Returns:
        List of recent document metadata.
        
    Raises:
        HTTPException: If retrieval fails.
    """
    try:
        logger.info(f"Fetching {limit} recent documents from database.")
        recent_doc_metadatas = get_recent_document_metadata(db, limit=limit)
        
        response_list = []
        for doc_meta in recent_doc_metadatas:
            # Calculate page_count (already a field in DocumentMetadata)
            page_count = doc_meta.page_count if doc_meta.page_count is not None else 0
            
            # Placeholder for duplicate_count. 
            # This would require more complex logic if it means related duplicate documents or pages.
            # For now, setting to 0 or a simple placeholder. 
            # If it means matched_doc_id is present, we can use that.
            duplicate_count = 1 if doc_meta.matched_doc_id else 0 # Simplistic: 1 if it's a known duplicate of another

            response_list.append({
                "doc_id": doc_meta.doc_id,
                "filename": doc_meta.filename,
                "status": doc_meta.status,
                "upload_timestamp": doc_meta.upload_timestamp.isoformat() if doc_meta.upload_timestamp else None,
                "page_count": page_count,
                "duplicate_count": duplicate_count # Needs clarification on what this count represents
            })
            
        return response_list
    except Exception as e:
        logger.error(f"Error retrieving recent documents from database: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error retrieving recent documents: {str(e)}")