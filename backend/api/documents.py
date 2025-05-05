"""
Document-level API endpoints.
Provides routes for retrieving and manipulating documents.
"""

import os
import json
import logging
from fastapi import APIRouter, HTTPException, Query, Path, Body
from fastapi.responses import FileResponse, JSONResponse
from typing import List, Dict, Optional, Any
from datetime import datetime

from backend.models.schemas import DocumentAnalysis, DocumentStatusUpdate, RebuildRequest
from utils.page_tracker import get_pages_by_doc_id
from backend.services.rebuilder import rebuild_from_unique_pages, merge_documents
from utils.config import settings

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/documents", tags=["Documents"])

# File paths
DOCUMENT_METADATA_PATH = "storage/metadata/document_metadata.json"


@router.get("/{doc_id}/analysis", response_model=DocumentAnalysis)
async def get_document_analysis(doc_id: str):
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
        # Check if metadata file exists
        if not os.path.exists(DOCUMENT_METADATA_PATH):
            raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")
        
        # Load metadata
        with open(DOCUMENT_METADATA_PATH, "r") as f:
            metadata = json.load(f)
        
        # Check if document exists
        if doc_id not in metadata:
            raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")
        
        doc_metadata = metadata[doc_id]
        
        # Get pages from page tracker
        pages = get_pages_by_doc_id(doc_id)
        
        # Create response
        return {
            "doc_id": doc_id,
            "filename": doc_metadata.get("filename", "Unknown"),
            "status": doc_metadata.get("status", "pending"),
            "pages": pages,
            "duplicates": doc_metadata.get("duplicates", []),
            "lastReviewer": doc_metadata.get("lastReviewer"),
            "lastReviewedAt": doc_metadata.get("lastReviewedAt"),
            "reviewHistory": doc_metadata.get("reviewHistory", [])
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving document analysis: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error retrieving document analysis: {str(e)}")


@router.post("/{doc_id}/status")
async def update_document_status(doc_id: str, status_update: DocumentStatusUpdate):
    """
    Update the status of a document.
    
    Args:
        doc_id: Document identifier
        status_update: Status update data
        
    Returns:
        Success message
        
    Raises:
        HTTPException: If document is not found or update fails
    """
    try:
        # Check if metadata file exists
        if not os.path.exists(DOCUMENT_METADATA_PATH):
            raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")
        
        # Load metadata
        with open(DOCUMENT_METADATA_PATH, "r") as f:
            metadata = json.load(f)
        
        # Check if document exists
        if doc_id not in metadata:
            raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")
        
        # Update status
        metadata[doc_id]["status"] = status_update.action
        
        # Add reviewer information
        metadata[doc_id]["lastReviewer"] = status_update.reviewer
        metadata[doc_id]["lastReviewedAt"] = datetime.now().isoformat()
        
        # Add notes if provided
        if status_update.notes:
            if "reviewHistory" not in metadata[doc_id]:
                metadata[doc_id]["reviewHistory"] = []
            
            metadata[doc_id]["reviewHistory"].append({
                "reviewer": status_update.reviewer,
                "timestamp": datetime.now().isoformat(),
                "action": status_update.action,
                "notes": status_update.notes
            })
        
        # Save metadata
        with open(DOCUMENT_METADATA_PATH, "w") as f:
            json.dump(metadata, f, indent=2)
        
        # Move document to appropriate folder
        source_paths = [
            os.path.join(settings.DOCUMENT_PATH, "unique", f"{doc_id}.pdf"),
            os.path.join(settings.DOCUMENT_PATH, "deduplicated", f"{doc_id}.pdf"),
            os.path.join(settings.DOCUMENT_PATH, "flagged_for_review", f"{doc_id}.pdf")
        ]
        
        source_path = None
        for path in source_paths:
            if os.path.exists(path):
                source_path = path
                break
        
        if source_path:
            if status_update.action == "keep":
                dest_path = os.path.join(settings.DOCUMENT_PATH, "unique", f"{doc_id}.pdf")
            elif status_update.action == "archive":
                dest_path = os.path.join(settings.DOCUMENT_PATH, "deduplicated", f"{doc_id}.pdf")
            else:  # "pending"
                dest_path = os.path.join(settings.DOCUMENT_PATH, "flagged_for_review", f"{doc_id}.pdf")
            
            # Only move if destination is different
            if source_path != dest_path:
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                import shutil
                shutil.copy2(source_path, dest_path)  # Copy instead of move to preserve original
        
        return {"message": f"Document status updated to {status_update.action}"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating document status: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error updating document status: {str(e)}")


@router.post("/rebuild")
async def rebuild_document(rebuild_request: RebuildRequest):
    """
    Rebuild a document from selected pages.
    
    Args:
        rebuild_request: Rebuild request data
        
    Returns:
        Path to the rebuilt document
        
    Raises:
        HTTPException: If rebuild fails
    """
    try:
        # Generate output path
        output_filename = f"rebuilt_{rebuild_request.filename}"
        output_path = os.path.join(settings.TEMP_PATH, output_filename)
        
        # Create page selections
        page_selections = []
        for page_hash in rebuild_request.pages:
            from utils.page_tracker import get_page_metadata
            page_data = get_page_metadata(page_hash)
            
            if not page_data:
                continue
                
            doc_id = page_data.get("doc_id")
            page_num = page_data.get("page_num", 0)
            
            if not doc_id or not page_num:
                continue
                
            # Find source path
            source_paths = [
                os.path.join(settings.DOCUMENT_PATH, "unique", f"{doc_id}.pdf"),
                os.path.join(settings.DOCUMENT_PATH, "deduplicated", f"{doc_id}.pdf"),
                os.path.join(settings.DOCUMENT_PATH, "flagged_for_review", f"{doc_id}.pdf")
            ]
            
            source_path = None
            for path in source_paths:
                if os.path.exists(path):
                    source_path = path
                    break
            
            if not source_path:
                continue
                
            page_selections.append({
                "source_path": source_path,
                "page_number": page_num - 1,  # Convert to 0-based
                "doc_id": doc_id
            })
        
        # Rebuild document
        from backend.services.rebuilder import rebuild_document
        result_path = rebuild_document(output_path, page_selections)
        
        return {"path": result_path, "filename": output_filename}
    except Exception as e:
        logger.error(f"Error rebuilding document: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error rebuilding document: {str(e)}")


@router.get("/recent", response_model=List[Dict[str, Any]])
async def get_recent_documents(limit: int = 10):
    """
    Get the most recently uploaded documents.
    
    Args:
        limit: Maximum number of documents to return
        
    Returns:
        List of recent document metadata
        
    Raises:
        HTTPException: If retrieval fails
    """
    try:
        # Check if metadata file exists
        if not os.path.exists(DOCUMENT_METADATA_PATH):
            return []
        
        # Load metadata
        with open(DOCUMENT_METADATA_PATH, "r") as f:
            metadata = json.load(f)
        
        # Sort by upload timestamp
        sorted_docs = sorted(
            [
                {
                    "doc_id": doc_id,
                    "filename": data.get("filename", "Unknown"),
                    "status": data.get("status", "pending"),
                    "upload_timestamp": data.get("upload_timestamp"),
                    "page_count": len(data.get("pages", [])),
                    "duplicate_count": len(data.get("duplicates", []))
                }
                for doc_id, data in metadata.items()
                if "upload_timestamp" in data
            ],
            key=lambda x: x.get("upload_timestamp", ""),
            reverse=True
        )
        
        return sorted_docs[:limit]
    except Exception as e:
        logger.error(f"Error retrieving recent documents: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error retrieving recent documents: {str(e)}")