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
from similarity.search import find_similar_documents
from similarity.embedding import embed_text
from backend.services.rebuilder import extract_page_as_pdf

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
        
        # Try semantic search if available
        try:
            # Embed the query
            query_embedding = embed_text(query.text)
            
            # Find similar documents
            semantic_results = find_similar_documents(query_embedding, query.threshold, query.max_results)
            
            # TODO: Combine basic and semantic results
            # For now, just return basic results
        except Exception as e:
            logger.warning(f"Semantic search failed: {str(e)}")
        
        return basic_results
        
    except Exception as e:
        logger.error(f"Page search failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")