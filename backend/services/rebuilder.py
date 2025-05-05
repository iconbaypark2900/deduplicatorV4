"""
Service for reconstructing documents from selected pages.
Allows rebuilding PDFs with a subset of pages from original documents.
"""

import os
import fitz  # PyMuPDF
import tempfile
import logging
from typing import List, Dict, Any, Optional, Tuple

from utils.config import settings

# Configure logging
logger = logging.getLogger(__name__)


def rebuild_document(
    output_path: str,
    page_selections: List[Dict[str, Any]]
) -> str:
    """
    Create a new PDF document from selected pages of existing documents.
    
    Args:
        output_path: Path where the new document will be saved
        page_selections: List of dictionaries with information about pages to include
            Each dictionary should have:
                - source_path: Path to source PDF
                - page_number: Page number to extract (0-based)
                - doc_id: Document ID (optional)
        
    Returns:
        Path to the rebuilt document
        
    Raises:
        ValueError: If any source document is not found
        IOError: If the output document cannot be created
    """
    logger.info(f"Rebuilding document with {len(page_selections)} pages to {output_path}")
    
    try:
        # Create a new PDF document
        new_doc = fitz.open()
        
        # Add selected pages to the new document
        for i, selection in enumerate(page_selections):
            source_path = selection.get("source_path")
            page_number = selection.get("page_number")
            
            if not source_path or not os.path.exists(source_path):
                source_id = selection.get("doc_id")
                logger.warning(f"Source document not found: {source_path} (ID: {source_id})")
                
                # Try to find document from doc_id if source_path doesn't exist
                if source_id:
                    # Try in unique documents
                    alt_path = os.path.join(settings.DOCUMENT_PATH, "unique", f"{source_id}.pdf")
                    if os.path.exists(alt_path):
                        source_path = alt_path
                    else:
                        # Try in deduplicated documents
                        alt_path = os.path.join(settings.DOCUMENT_PATH, "deduplicated", f"{source_id}.pdf")
                        if os.path.exists(alt_path):
                            source_path = alt_path
                        else:
                            # Try in flagged documents
                            alt_path = os.path.join(settings.DOCUMENT_PATH, "flagged_for_review", f"{source_id}.pdf")
                            if os.path.exists(alt_path):
                                source_path = alt_path
            
            if not source_path or not os.path.exists(source_path):
                logger.error(f"Could not find source document for page {i}")
                continue
            
            try:
                source_doc = fitz.open(source_path)
                
                # Validate page number
                if page_number < 0 or page_number >= len(source_doc):
                    logger.warning(f"Invalid page number {page_number} for document {source_path}")
                    continue
                
                # Add the page to the new document
                new_doc.insert_pdf(source_doc, from_page=page_number, to_page=page_number)
                logger.debug(f"Added page {page_number} from {source_path}")
                
                source_doc.close()
                
            except Exception as e:
                logger.error(f"Error processing page {page_number} from {source_path}: {e}")
        
        # Save the new document
        new_doc.save(output_path)
        new_doc.close()
        
        logger.info(f"Successfully rebuilt document with {len(page_selections)} pages at {output_path}")
        return output_path
        
    except Exception as e:
        logger.error(f"Failed to rebuild document: {e}")
        raise IOError(f"Failed to rebuild document: {e}")


def rebuild_from_unique_pages(
    doc_id: str,
    output_path: Optional[str] = None
) -> str:
    """
    Rebuild a document from its unique pages only, removing duplicates.
    
    Args:
        doc_id: Document identifier
        output_path: Output path (optional - will be generated if not provided)
        
    Returns:
        Path to the rebuilt document
        
    Raises:
        ValueError: If the document is not found or has no metadata
    """
    from utils.page_tracker import load_page_hash_map
    
    # Load page hash map
    page_map = load_page_hash_map()
    
    # Find all pages for this document
    doc_pages = []
    duplicate_hashes = set()
    
    for hash, page_data in page_map.items():
        if page_data.get("doc_id") == doc_id:
            doc_pages.append({
                "hash": hash,
                "page_num": page_data.get("page_num", 0),
                "is_duplicate": False
            })
        elif "duplicates" in page_data:
            # Check if this page is a duplicate of a page in our document
            for dup in page_data.get("duplicates", []):
                if dup.get("doc_id") == doc_id:
                    duplicate_hashes.add(hash)
    
    # Mark pages as duplicates if they appear in the duplicate set
    for page in doc_pages:
        if page["hash"] in duplicate_hashes:
            page["is_duplicate"] = True
    
    # Sort by page number
    doc_pages.sort(key=lambda x: x["page_num"])
    
    # Get source document path
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
        raise ValueError(f"Document {doc_id} not found")
    
    # Create page selections for non-duplicate pages
    page_selections = [
        {
            "source_path": source_path,
            "page_number": page["page_num"] - 1,  # Convert to 0-based
            "doc_id": doc_id
        }
        for page in doc_pages if not page["is_duplicate"]
    ]
    
    # Generate output path if not provided
    if not output_path:
        output_path = os.path.join(settings.DOCUMENT_PATH, "deduplicated", f"{doc_id}_unique.pdf")
    
    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Rebuild the document
    return rebuild_document(output_path, page_selections)


def extract_page_as_pdf(doc_id: str, page_num: int, output_path: Optional[str] = None) -> str:
    """
    Extract a single page from a document and save it as a separate PDF.
    
    Args:
        doc_id: Document identifier
        page_num: Page number (1-based)
        output_path: Output path (optional - will be generated if not provided)
        
    Returns:
        Path to the extracted page
        
    Raises:
        ValueError: If the document or page is not found
    """
    # Get source document path
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
        raise ValueError(f"Document {doc_id} not found")
    
    # Generate output path if not provided
    if not output_path:
        output_path = os.path.join(settings.TEMP_PATH, f"{doc_id}_page{page_num}.pdf")
    
    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    try:
        # Open source document
        source_doc = fitz.open(source_path)
        
        # Validate page number
        if page_num < 1 or page_num > len(source_doc):
            source_doc.close()
            raise ValueError(f"Invalid page number {page_num} for document {doc_id}")
        
        # Create a new document with this page
        new_doc = fitz.open()
        new_doc.insert_pdf(source_doc, from_page=page_num-1, to_page=page_num-1)
        new_doc.save(output_path)
        
        new_doc.close()
        source_doc.close()
        
        return output_path
        
    except Exception as e:
        logger.error(f"Failed to extract page {page_num} from {doc_id}: {e}")
        raise


def merge_documents(doc_ids: List[str], output_path: Optional[str] = None) -> str:
    """
    Merge multiple documents into a single PDF.
    
    Args:
        doc_ids: List of document identifiers
        output_path: Output path (optional - will be generated if not provided)
        
    Returns:
        Path to the merged document
        
    Raises:
        ValueError: If any document is not found
    """
    # Generate output path if not provided
    if not output_path:
        output_path = os.path.join(settings.TEMP_PATH, f"merged_{'_'.join(doc_ids[:2])}.pdf")
        if len(doc_ids) > 2:
            output_path = os.path.join(settings.TEMP_PATH, f"merged_{doc_ids[0]}_and_{len(doc_ids)-1}_others.pdf")
    
    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Find source documents
    source_docs = []
    
    for doc_id in doc_ids:
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
            logger.warning(f"Document {doc_id} not found")
            continue
        
        source_docs.append({"doc_id": doc_id, "path": source_path})
    
    if not source_docs:
        raise ValueError("No valid documents found to merge")
    
    try:
        # Create a new document
        new_doc = fitz.open()
        
        # Add each document
        for doc_info in source_docs:
            source_doc = fitz.open(doc_info["path"])
            new_doc.insert_pdf(source_doc)
            source_doc.close()
        
        # Save the merged document
        new_doc.save(output_path)
        new_doc.close()
        
        return output_path
        
    except Exception as e:
        logger.error(f"Failed to merge documents: {e}")
        raise