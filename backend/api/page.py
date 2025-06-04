"""
Page-level API endpoints.
Provides routes for retrieving and manipulating document pages.
"""

import os
from fastapi import APIRouter, HTTPException, Query, Path, Depends
from fastapi.responses import FileResponse, JSONResponse
from typing import List, Dict, Optional, Any
import logging

from sqlalchemy.orm import Session
from utils.database import get_db, Page

from backend.models.schemas import PageMetadataResponse, PageSimilarityQuery
from utils.page_tracker import (
    get_page_info_by_hash,
    update_page_review_status,
    find_page_duplicates,
    search_page_text_snippets
)
from backend.services.rebuilder import extract_page_as_pdf
from backend.services.image_service import get_page_image_path, get_page_image_url, get_all_page_images

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/page", tags=["Pages"])

# Helper function to convert Page SQLAlchemy model to dictionary for API responses
def _convert_page_to_api_dict(page: Page, original_hash_for_duplicates: Optional[str] = None) -> Dict[str, Any]:
    """
    Converts a Page SQLAlchemy object to a dictionary suitable for API responses.
    Ensures that document relationship is accessed to load filename.
    """
    filename = "Unknown"
    if page.document: # Accessing relationship, ensure session is active
        filename = page.document.filename
    
    data = {
        "page_id": page.id,
        "page_hash": page.page_hash,
        "page_num": page.page_number,
        "doc_id": page.document_id,
        "filename": filename,
        "status": page.status,
        "text_snippet": page.text_snippet[:250] if page.text_snippet else "", # Truncated snippet
        "image_path": page.page_image_path, # This is the raw path
        # "image_url": get_page_image_url(page.page_hash) if page.page_hash else None, # Alternative if using URL generation
        "medical_confidence": page.medical_confidence,
        "duplicate_confidence": page.duplicate_confidence,
        # Add other relevant fields from Page model as needed by front-end
    }
    if original_hash_for_duplicates:
        data["original_hash"] = original_hash_for_duplicates
    return data


@router.get("/{page_hash}", response_model=PageMetadataResponse)
async def get_page_info(page_hash: str, db: Session = Depends(get_db)):
    """
    Get metadata for a specific page.
    
    Args:
        page_hash: Page hash identifier
        
    Returns:
        Page metadata
        
    Raises:
        HTTPException: If page is not found
    """
    page_obj = get_page_info_by_hash(db, page_hash)
    
    if not page_obj:
        raise HTTPException(status_code=404, detail=f"Page {page_hash} not found")
    
    # Ensure document is loaded for filename
    filename = "Unknown"
    if page_obj.document: # This will trigger a load if not already loaded
        filename = page_obj.document.filename
    
    return PageMetadataResponse(
        page_hash=page_obj.page_hash,
        page_num=page_obj.page_number,
        filename=filename,
        doc_id=page_obj.document_id
    )


@router.get("/{page_hash}/image")
async def get_page_image(page_hash: str, db: Session = Depends(get_db)):
    """
    Get the image for a specific page.
    
    Args:
        page_hash: Page hash identifier
        
    Returns:
        Page image
        
    Raises:
        HTTPException: If page is not found or has no image
    """
    page_obj = get_page_info_by_hash(db, page_hash)
    
    if not page_obj:
        raise HTTPException(status_code=404, detail=f"Page {page_hash} not found")
    
    image_path = page_obj.page_image_path
    
    if not image_path or not os.path.exists(image_path):
        # Fallback logic for images in storage/tmp (can be reviewed/simplified)
        # This fallback is less critical if page_image_path is reliably populated.
        # The old fallback based on parsing page_hash is brittle.
        # A better fallback might involve querying by doc_id and page_number if page_hash is not found,
        # but that's beyond current scope.
        logger.warning(f"Image path {image_path} for page hash {page_hash} not found or invalid. Fallback not implemented here for DB-centric approach.")
        # For now, if not in DB, it's a 404.
        raise HTTPException(status_code=404, detail=f"Image not found for page {page_hash}. Path: {image_path}")
    
    return FileResponse(image_path)


@router.get("/{page_hash}/pdf")
async def get_page_pdf(page_hash: str, db: Session = Depends(get_db)):
    """
    Get a PDF containing just this page.
    
    Args:
        page_hash: Page hash identifier
        
    Returns:
        PDF file with just this page
        
    Raises:
        HTTPException: If page is not found or PDF generation fails
    """
    page_obj = get_page_info_by_hash(db, page_hash)
    
    if not page_obj:
        raise HTTPException(status_code=404, detail=f"Page {page_hash} not found")
    
    doc_id = page_obj.document_id
    page_num = page_obj.page_number
    
    # Ensure document is loaded for filename
    source_filename = "UnknownDocument"
    if page_obj.document:
        source_filename = page_obj.document.filename
    
    if not doc_id or not page_num: # page_num should always be > 0
        raise HTTPException(status_code=404, detail=f"Incomplete metadata (doc_id or page_num missing) for page {page_hash}")
    
    try:
        # extract_page_as_pdf needs doc_id (actual ID) and page_num
        # It also needs the source PDF path, which it currently reconstructs based on doc_id.
        # We should verify extract_page_as_pdf correctly gets the source PDF path
        # from DocumentMetadata.file_path using the doc_id.
        pdf_page_path = extract_page_as_pdf(doc_id, page_num, db_session=db) # Pass db session if needed by rebuilder
        
        output_filename = f"{os.path.splitext(source_filename)[0]}_page{page_num}.pdf"
        
        return FileResponse(
            pdf_page_path,
            media_type="application/pdf",
            filename=output_filename
        )
    except FileNotFoundError as fnf_error:
        logger.error(f"Source PDF for doc_id {doc_id} not found by rebuilder: {str(fnf_error)}", exc_info=True)
        raise HTTPException(status_code=404, detail=f"Source PDF for page {page_hash} (doc_id: {doc_id}) not found.")
    except Exception as e:
        logger.error(f"Error extracting page PDF for {page_hash}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF for page {page_hash}: {str(e)}")


@router.get("/{page_hash}/duplicates", response_model=List[Dict[str, Any]])
async def get_page_duplicates(page_hash: str, db: Session = Depends(get_db)):
    """
    Get duplicates of a specific page.
    
    Args:
        page_hash: Page hash identifier
        
    Returns:
        List of duplicate pages
        
    Raises:
        HTTPException: If page is not found
    """
    source_page = get_page_info_by_hash(db, page_hash)
    
    if not source_page:
        raise HTTPException(status_code=404, detail=f"Page with hash {page_hash} not found, cannot get duplicates.")
    
    # find_page_duplicates now expects page_hash and uses get_page_info_by_hash internally
    duplicate_page_objects = find_page_duplicates(db, page_hash)
    
    # Convert Page objects to dicts for response
    return [_convert_page_to_api_dict(dup_page, original_hash_for_duplicates=page_hash) for dup_page in duplicate_page_objects]


@router.post("/{page_hash}/status")
async def update_page_review_status_endpoint(
    page_hash: str,
    status: str,
    reviewer: str,
    notes: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Update the review status of a page.
    
    Args:
        page_hash: Page hash identifier
        status: New status for the page
        reviewer: Identifier of the reviewer
        notes: Optional notes about the decision
        
    Returns:
        Success message
        
    Raises:
        HTTPException: If page is not found or update fails
    """
    success = update_page_review_status(
        db=db, 
        page_hash=page_hash, 
        decision=status,
        reviewer_username=reviewer, 
        notes=notes
    )
    
    if not success:
        raise HTTPException(status_code=400, detail=f"Failed to update page {page_hash}. Check logs for details (e.g. page or user not found).")
    
    # Logic to update duplicates:
    # When a page's status is updated, its duplicates should also be updated.
    # This is complex: what if the duplicate was already reviewed with a different status?
    # For now, let's assume a simple propagation: if this page is marked X, its duplicates are also marked X.
    # This might need more nuanced handling based on product requirements.
    
    # Fetch the source page again to get its ID for duplicate note referencing if needed
    source_page_for_note = get_page_info_by_hash(db, page_hash)
    source_page_id_for_note = source_page_for_note.id if source_page_for_note else "unknown"

    duplicate_page_objs = find_page_duplicates(db, page_hash)
    updated_duplicates_count = 0
    for dup_page_obj in duplicate_page_objs:
        # Avoid re-updating the original page if it somehow appeared in its own duplicate list
        if dup_page_obj.page_hash == page_hash:
            continue

        dup_success = update_page_review_status(
            db=db,
            page_hash=dup_page_obj.page_hash,
            decision=status,
            reviewer_username=reviewer,
            notes=f"Automatically updated as duplicate of page hash {page_hash} (ID: {source_page_id_for_note}). Original note: {notes if notes else ''}"
        )
        if dup_success:
            updated_duplicates_count += 1
        else:
            logger.warning(f"Failed to auto-update status for duplicate page {dup_page_obj.page_hash} of {page_hash}")
            
    db.commit()

    return {
        "message": f"Page status updated to {status}. {updated_duplicates_count} duplicate(s) also updated."
    }


@router.post("/search", response_model=List[Dict[str, Any]])
async def search_pages(query: PageSimilarityQuery, db: Session = Depends(get_db)):
    """
    Search for pages that match the query text.
    
    Args:
        query: Search parameters including text, threshold, and max results
        
    Returns:
        List of matching pages with similarity scores
        
    Raises:
        HTTPException: If search fails
    """
    try:
        page_objects = search_page_text_snippets(db, query.text, query.max_results)
        
        return [_convert_page_to_api_dict(page) for page in page_objects]
        
    except Exception as e:
        logger.error(f"Page search failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/number/{page_number}/image")
async def get_image_by_page_number(page_number: int):
    """
    Get an image directly by page number.
    This is a more direct route to find images without needing to know the page hash.
    
    Args:
        page_number: The page number to find (1-based index)
        
    Returns:
        Page image
        
    Raises:
        HTTPException: If no image is found for the page number
    """
    # Use our image service to find the image
    image_path = get_page_image_path(page_number)
    
    if not image_path or not os.path.exists(image_path):
        # Try to look in the tmp directory as a fallback
        tmp_dir = "storage/tmp"
        
        # Look for any file matching the pattern page{page_number}_*.png
        if os.path.exists(tmp_dir):
            for filename in os.listdir(tmp_dir):
                if filename.startswith(f"page{page_number}_") and filename.endswith(".png"):
                    return FileResponse(os.path.join(tmp_dir, filename))
                    
        raise HTTPException(status_code=404, detail=f"No image found for page {page_number}")
    
    return FileResponse(image_path)


@router.get("/debug/image-mapping")
async def get_image_mapping_status():
    """
    Debug endpoint to check the state of the image mapping service.
    Returns the current mapping of page numbers to image files.
    
    Returns:
        Mapping information and statistics
    """
    # Get all page images
    image_map = get_all_page_images()
    
    # Build a response with useful information
    result = {
        "total_page_numbers": len(image_map),
        "page_counts": {str(page_num): len(files) for page_num, files in image_map.items()},
        "mapping": {}
    }
    
    # Add the first few mappings for inspection
    for page_num, files in image_map.items():
        if len(result["mapping"]) < 10:  # Limit to 10 entries to avoid overwhelmingly large response
            result["mapping"][str(page_num)] = [
                {"filename": f, "url": f"/temp/{f}"} for f in files[:3]  # Show up to 3 files per page
            ]
    
    return result