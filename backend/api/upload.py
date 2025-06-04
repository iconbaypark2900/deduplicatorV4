"""
Upload API endpoints for handling file uploads and analysis.
"""

from fastapi import APIRouter, UploadFile, HTTPException, File, Form, Depends
from backend.services.extractor import extract_text_and_pages
from similarity.tfidf import analyze_document_pages
from backend.services.logger import log_upload
from backend.models.schemas import UploadResponse
from utils.duplicate_analysis import (
    compute_document_hash,
    compute_document_tfidf_vector
)
from utils.page_tracker import update_page_hash_map
from similarity.engine import SimilarityEngine
from utils.database import get_db, DocumentMetadata, Page, PageDuplicate, upsert_document_metadata, create_page, create_page_duplicate
from sqlalchemy.orm import Session
import uuid
import os
from datetime import datetime
from typing import List
import tempfile
import logging

# Set up logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(tags=["Upload"])


@router.post("/", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Upload and analyze a single document.
    
    Args:
        file: PDF file to upload
        
    Returns:
        UploadResponse with analysis results
        
    Raises:
        HTTPException: If upload or analysis fails
    """
    logger.debug(f"Received upload request for file: {file.filename}")
    
    if not file.filename.endswith('.pdf'):
        logger.warning(f"Rejected non-PDF file: {file.filename}")
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    temp_path = None
    try:
        # Generate doc_id
        doc_id = str(uuid.uuid4())
        temp_path = f"storage/tmp/{doc_id}_{file.filename}"
        
        # Save uploaded file
        logger.debug(f"Saving uploaded file to {temp_path}")
        with open(temp_path, "wb") as f:
            content = await file.read()
            f.write(content)

        # Create directories for page images
        os.makedirs("storage/page_images", exist_ok=True)

        # Extract text and analyze
        full_text, pages_data = extract_text_and_pages(temp_path, doc_id=doc_id)
        
        # Update page hash map with the extracted pages
        logger.debug("Updating page hash map")
        page_texts = [p['text'] for p in pages_data]
        medical_confidences = [p.get('medical_confidence', 0.0) for p in pages_data]
        duplicate_confidences = [p.get('duplicate_confidence', 0.0) for p in pages_data]
        
        # Create page images and store their paths
        image_paths = []
        for i, page_data in enumerate(pages_data, 1):
            # Generate page images using PyMuPDF or pdf2image
            # This would be implemented in a page rendering service
            image_path = f"storage/page_images/{doc_id}_page{i}.png"
            image_paths.append(image_path)
        
        # Update page hash map
        update_page_hash_map(
            doc_id=doc_id,
            filename=file.filename,
            page_texts=page_texts,
            medical_confidences=medical_confidences,
            duplicate_confidences=duplicate_confidences,
            image_paths=image_paths
        )

        # Analyze pages for duplicates
        try:
            logger.debug("Starting page analysis")
            similar_pairs = analyze_document_pages(pages_data)
            logger.debug(f"Found {len(similar_pairs)} similar page pairs")
            
            # Convert to page metadata format
            page_metadata = []
            for i, page in enumerate(pages_data):
                page_metadata.append({
                    "page_num": i + 1,
                    "page_hash": page["page_hash"],
                    "text_snippet": page["text_snippet"]
                })
            
            # Find duplicates
            duplicates = []
            for pair in similar_pairs:
                page1_idx = pair["page1_idx"]
                page2_idx = pair["page2_idx"]
                similarity = pair["similarity"]
                
                logger.debug(f"Duplicate found: pages {page1_idx} and {page2_idx} with similarity {similarity}")
                duplicates.append({
                    "page1_idx": page1_idx,
                    "page2_idx": page2_idx,
                    "similarity": similarity
                })
            
            # Determine overall status
            status = "duplicate" if duplicates else "unique"
            logger.debug(f"Document status: {status}")
            
        except Exception as e:
            logger.error(f"Page analysis failed: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to analyze document: {str(e)}")

        # Store document metadata in the database
        try:
            logger.debug("Storing document metadata in DB")
            
            # Compute document hash
            document_content_hash = compute_document_hash(temp_path)
            if not document_content_hash:
                logger.warning(f"Could not compute content hash for {file.filename} at {temp_path}. Proceeding without it.")
                # Decide if this is a critical failure. For now, allow proceeding.
            
            # Upsert DocumentMetadata
            db_document = upsert_document_metadata(
                db=db,
                doc_id=doc_id,
                filename=file.filename,
                status=status,
                upload_timestamp=datetime.utcnow(),
                page_count=len(page_metadata),
                content_hash=document_content_hash,
                file_path=temp_path
            )
            
            # Store Page information
            db_pages = {} # To map page_idx to Page object for duplicate creation
            for i, p_meta in enumerate(page_metadata):
                db_page = create_page(
                    db=db,
                    document_id=doc_id,
                    page_number=p_meta["page_num"], # page_metadata is 1-indexed from earlier
                    page_hash=p_meta["page_hash"],
                    text_snippet=p_meta["text_snippet"],
                    # image_paths are already handled by update_page_hash_map for now
                    # We might need to consolidate this if update_page_hash_map is also refactored
                )
                db_pages[i] = db_page # page_metadata used 0-indexed loop for pages_data

            # Store DuplicatePair information
            # The 'duplicates' list contains page1_idx and page2_idx which are 0-indexed
            for dup_pair in duplicates:
                page1_db_id = None
                page2_db_id = None

                # Find the corresponding Page objects from db_pages
                # The indices in dup_pair (page1_idx, page2_idx) correspond to the original pages_data list
                # And page_metadata was created by iterating pages_data with enumerate
                
                # Check if page1_idx and page2_idx are valid keys in db_pages
                if dup_pair["page1_idx"] in db_pages:
                    page1_db_id = db_pages[dup_pair["page1_idx"]].id
                else:
                    logger.error(f"Could not find page with original index {dup_pair['page1_idx']} in db_pages for doc {doc_id}")
                    continue

                if dup_pair["page2_idx"] in db_pages:
                    page2_db_id = db_pages[dup_pair["page2_idx"]].id
                else:
                    logger.error(f"Could not find page with original index {dup_pair['page2_idx']} in db_pages for doc {doc_id}")
                    continue
                
                if page1_db_id and page2_db_id:
                    create_page_duplicate(
                        db=db,
                        source_page_id=page1_db_id,
                        duplicate_page_id=page2_db_id,
                        similarity=dup_pair["similarity"]
                    )
                else:
                    logger.warning(f"Could not create PageDuplicate for pair {dup_pair} due to missing page IDs.")
            
            db.commit() # Commit all changes for this document
            logger.info(f"Successfully stored metadata for document {doc_id} in DB")
                
        except Exception as e:
            db.rollback() # Rollback in case of error
            logger.error(f"Failed to store metadata in DB: {str(e)}", exc_info=True)
            # Not raising HTTPException here to allow logging and response, but original code had a warning
            # Re-evaluating if this should be a critical failure or just a warning.
            # For now, let's maintain the original behavior of logging a warning and continuing.
            logger.warning(f"Failed to store document metadata in DB: {str(e)}")

        # Log the upload
        try:
            logger.debug("Logging upload")
            log_upload(doc_id=doc_id, filename=file.filename, status=status)
        except Exception as e:
            logger.error(f"Logging failed: {str(e)}", exc_info=True)
            logger.warning(f"Failed to log upload: {str(e)}")

        # Return structured response
        response = UploadResponse(
            doc_id=doc_id,
            status=status,
            match=None,
            pages=page_metadata,
            duplicates=duplicates
        )
        logger.debug(f"Returning response: {response}")
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
    finally:
        # Clean up temporary file
        try:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)
                logger.debug(f"Cleaned up temp file: {temp_path}")
        except Exception as e:
            logger.error(f"Cleanup failed: {str(e)}", exc_info=True)
            logger.warning(f"Failed to clean up temporary file: {str(e)}")


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