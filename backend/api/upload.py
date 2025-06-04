"""
Upload API endpoints for handling file uploads and analysis.
"""

from fastapi import APIRouter, UploadFile, HTTPException, File
import uuid
import os
import logging

from backend.tasks.pipeline_tasks import process_document_task
from backend.models.schemas import AsyncUploadResponse
from utils.config import settings, get_temp_path
from utils.duplicate_analysis import compute_document_hash, compute_document_tfidf_vector
from similarity.engine import SimilarityEngine
from typing import List
import tempfile

# Set up logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(tags=["Upload"])



@router.post("/", response_model=AsyncUploadResponse)
async def upload_document(file: UploadFile = File(...)):
    """
    Upload a PDF and initiate background processing.

    Args:
        file: PDF file to upload

    Returns:
        An object containing the document ID and Celery task ID

    Raises:
        HTTPException: If upload fails
    """
    logger.debug(f"Received upload request for file: {file.filename}")

    if not file.filename.endswith(".pdf"):
        logger.warning(f"Rejected non-PDF file: {file.filename}")
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    temp_path = None
    try:
        doc_id = str(uuid.uuid4())
        temp_path = get_temp_path(f"{doc_id}_{file.filename}")

        logger.debug(f"Saving uploaded file to {temp_path}")
        with open(temp_path, "wb") as f:
            content = await file.read()
            f.write(content)

        celery_task = process_document_task.delay(temp_path, file.filename, doc_id)

        logger.debug(f"Queued Celery task {celery_task.id} for {doc_id}")
        return {"message": "File queued for processing", "doc_id": doc_id, "task_id": celery_task.id}

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.post("/batch")
async def analyze_batch_folder(files: List[UploadFile] = File(...)):
    """
    Analyze a batch of documents for duplicates.
    
    Args:
        files: List of PDF files to analyze
        
    Returns:
        Dictionary with analysis results
        
    Raises:
        HTTPException: If analysis fails
    """
    try:
        # Save uploaded files temporarily
        temp_files = []
        document_entries = []
        
        for file in files:
            if not file.filename.endswith('.pdf'):
                logger.warning(f"Skipping non-PDF file: {file.filename}")
                continue
                
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
                content = await file.read()
                if not content:
                    logger.warning(f"Skipping empty file: {file.filename}")
                    continue
                    
                tmp.write(content)
                temp_files.append(tmp.name)
                
                # Process each document
                doc_hash = compute_document_hash(tmp.name)
                if doc_hash is None:
                    logger.warning(f"Failed to compute hash for: {file.filename}")
                    continue
                    
                # Get document TF-IDF vector
                vector = compute_document_tfidf_vector(tmp.name)
                if vector is None:
                    logger.warning(f"Failed to compute TF-IDF vector for: {file.filename}")
                    continue
                    
                document_entries.append({
                    "filename": file.filename,
                    "path": tmp.name,
                    "hash": doc_hash,
                    "tfidf_vector": vector
                })

        if not document_entries:
            raise HTTPException(status_code=400, detail="No valid PDF files were uploaded")

        # Compare documents for exact and near duplicates
        results = {
            "exact_duplicates": [],
            "near_duplicates": []
        }
        
        # Find exact duplicates by hash
        hash_to_docs = {}
        for entry in document_entries:
            if entry["hash"] not in hash_to_docs:
                hash_to_docs[entry["hash"]] = []
            hash_to_docs[entry["hash"]].append(entry)
        
        # Report exact duplicates
        for doc_hash, docs in hash_to_docs.items():
            if len(docs) > 1:
                for i in range(len(docs)):
                    for j in range(i+1, len(docs)):
                        results["exact_duplicates"].append({
                            "file1": docs[i]["filename"],
                            "file2": docs[j]["filename"],
                            "type": "exact_duplicate"
                        })
        
        # Find near duplicates by vector similarity
        for i in range(len(document_entries)):
            for j in range(i+1, len(document_entries)):
                # Skip if already identified as exact duplicates
                if document_entries[i]["hash"] == document_entries[j]["hash"]:
                    continue
                    
                # Compute similarity
                engine = SimilarityEngine()
                sim = engine.compute_similarity(
                    document_entries[i]["tfidf_vector"], 
                    document_entries[j]["tfidf_vector"]
                )
                
                if sim > 0.9:  # High similarity threshold
                    results["near_duplicates"].append({
                        "file1": document_entries[i]["filename"],
                        "file2": document_entries[j]["filename"],
                        "type": "near_duplicate",
                        "similarity": float(sim)
                    })

        # Clean up temporary files
        for tmp_path in temp_files:
            try:
                os.unlink(tmp_path)
            except Exception as e:
                logger.warning(f"Failed to clean up temp file {tmp_path}: {str(e)}")

        # Combine results
        combined_results = results["exact_duplicates"] + results["near_duplicates"]
        return {
            "total_documents": len(document_entries),
            "exact_duplicates": len(results["exact_duplicates"]),
            "near_duplicates": len(results["near_duplicates"]),
            "duplicates": combined_results
        }

    except HTTPException:
        raise
    except Exception as e:
        # Clean up any remaining temporary files
        for tmp_path in temp_files:
            try:
                os.unlink(tmp_path)
            except:
                pass
        logger.error(f"Batch analysis failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch analysis failed: {str(e)}")