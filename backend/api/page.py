"""
Page-level API endpoints.
Provides routes for retrieving and manipulating document pages.
"""

import os
from fastapi import APIRouter, HTTPException, Query, Path
from fastapi.responses import FileResponse, JSONResponse
from typing import List, Dict, Optional, Any
import logging

from backend.models.schemas import PageMetadataResponse, PageSimilarityQuery
from utils.page_tracker import (
    get_page_metadata, 
    update_page_status,
    find_duplicates_of_page,
    search_page_snippets
)
from backend.services.rebuilder import extract_page_as_pdf
from backend.services.image_service import get_page_image_path, get_page_image_url, get_all_page_images

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/page", tags=["Pages"])


@router.get("/{page_hash}", response_model=PageMetadataResponse)
async def get_page_info(page_hash: str):
    """
    Get metadata for a specific page.
    
    Args:
        page_hash: Page hash identifier
        
    Returns:
        Page metadata
        
    Raises:
        HTTPException: If page is not found
    """
    page_data = get_page_metadata(page_hash)
    
    if not page_data:
        raise HTTPException(status_code=404, detail=f"Page {page_hash} not found")
    
    return {
        "page_hash": page_hash,
        "page_num": page_data.get("page_num", 0),
        "filename": page_data.get("source_doc", "Unknown"),
        "doc_id": page_data.get("doc_id"),
        "pdf_path": None  # We don't expose the full path to clients
    }


@router.get("/{page_hash}/image")
async def get_page_image(page_hash: str):
    """
    Get the image for a specific page.
    
    Args:
        page_hash: Page hash identifier
        
    Returns:
        Page image
        
    Raises:
        HTTPException: If page is not found or has no image
    """
    page_data = get_page_metadata(page_hash)
    
    if not page_data:
        raise HTTPException(status_code=404, detail=f"Page {page_hash} not found")
    
    image_path = page_data.get("image_path")
    if not image_path or not os.path.exists(image_path):
        # Try to find the image in the tmp directory as a fallback
        tmp_dir = "storage/tmp"
        
        # First check if the page_hash is actually a page number
        try:
            # See if it's a number like "1", "2", etc.
            page_number = int(page_hash)
            
            # Look for any file matching the pattern page{page_number}_*.png
            for filename in os.listdir(tmp_dir):
                if filename.startswith(f"page{page_number}_") and filename.endswith(".png"):
                    return FileResponse(os.path.join(tmp_dir, filename))
        except (ValueError, TypeError):
            # Not a number, continue with normal processing
            pass
            
        # If page_hash contains "_page", it might be a doc_id_pageN format
        if "_page" in page_hash:
            try:
                parts = page_hash.split("_page")
                if len(parts) == 2:
                    doc_id, page_number = parts
                    # Look for any file matching the pattern page{page_number}_*.png
                    for filename in os.listdir(tmp_dir):
                        if filename.startswith(f"page{page_number}_") and filename.endswith(".png"):
                            return FileResponse(os.path.join(tmp_dir, filename))
            except Exception:
                # Failed to parse, continue with normal processing
                pass
                
        raise HTTPException(status_code=404, detail=f"No image available for page {page_hash}")
    
    return FileResponse(image_path)


@router.get("/{page_hash}/pdf")
async def get_page_pdf(page_hash: str):
    """
    Get a PDF containing just this page.
    
    Args:
        page_hash: Page hash identifier
        
    Returns:
        PDF file with just this page
        
    Raises:
        HTTPException: If page is not found or PDF generation fails
    """
    page_data = get_page_metadata(page_hash)
    
    if not page_data:
        raise HTTPException(status_code=404, detail=f"Page {page_hash} not found")
    
    doc_id = page_data.get("doc_id")
    page_num = page_data.get("page_num", 0)
    filename = page_data.get("source_doc", "Unknown")
    
    if not doc_id or not page_num:
        raise HTTPException(status_code=404, detail=f"Incomplete metadata for page {page_hash}")
    
    try:
        # Extract the page as a PDF
        pdf_path = extract_page_as_pdf(doc_id, page_num)
        
        # Generate a sensible filename
        output_filename = f"{os.path.splitext(filename)[0]}_page{page_num}.pdf"
        
        return FileResponse(
            pdf_path,
            media_type="application/pdf",
            filename=output_filename
        )
    except Exception as e:
        logger.error(f"Error extracting page PDF: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {str(e)}")


@router.get("/{page_hash}/duplicates", response_model=List[Dict[str, Any]])
async def get_page_duplicates(page_hash: str):
    """
    Get duplicates of a specific page.
    
    Args:
        page_hash: Page hash identifier
        
    Returns:
        List of duplicate pages
        
    Raises:
        HTTPException: If page is not found
    """
    page_data = get_page_metadata(page_hash)
    
    if not page_data:
        raise HTTPException(status_code=404, detail=f"Page {page_hash} not found")
    
    duplicates = find_duplicates_of_page(page_hash)
    
    # Add the original page hash to each duplicate for reference
    for dup in duplicates:
        dup["original_hash"] = page_hash
    
    return duplicates


@router.post("/{page_hash}/status")
async def update_page_review_status(
    page_hash: str,
    status: str,
    reviewer: str,
    notes: Optional[str] = None
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
    success = update_page_status(page_hash, status, reviewer, notes)
    
    if not success:
        raise HTTPException(status_code=404, detail=f"Failed to update page {page_hash}")
    
    # Also update any duplicates of this page
    duplicates = find_duplicates_of_page(page_hash)
    for dup in duplicates:
        dup_hash = dup.get("page_hash")
        if dup_hash:
            update_page_status(dup_hash, status, reviewer, f"Automatically updated as duplicate of {page_hash}")
    
    return {"message": f"Page status updated to {status}"}


@router.post("/search", response_model=List[Dict[str, Any]])
async def search_pages(query: PageSimilarityQuery):
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
        # Simple text search
        basic_results = search_page_snippets(query.text, query.max_results)
        
        return basic_results
        
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