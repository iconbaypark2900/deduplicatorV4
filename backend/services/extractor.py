"""
PDF text extraction service.
Extracts and processes text from PDF documents.
"""

import os
import uuid
import logging
from typing import Tuple, List, Dict, Any, Optional

from ingestion.pdf_reader import extract_text_from_pdf, extract_pages_from_pdf
from ingestion.preprocessing import normalize_medical_text, measure_medical_confidence, extract_medical_terms
from utils.page_tracker import hash_text
from similarity.hashing import compute_document_hash
from utils.duplicate_analysis import compute_document_tfidf_vector

# Configure logging
logger = logging.getLogger(__name__)


def extract_text_and_pages(pdf_path: str, doc_id: str = None) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Extract text from a PDF file and normalize it.
    Also extracts page-level information and converts to structured format.
    
    Args:
        pdf_path: Path to the PDF file
        doc_id: Document identifier (optional)
        
    Returns:
        Tuple of (full_text, list of page data dictionaries)
        
    Raises:
        Exception: If text extraction fails
    """
    logger.debug(f"Extracting text and pages from {pdf_path}")
    
    # Generate document ID if not provided
    if not doc_id:
        doc_id = str(uuid.uuid4())
    
    try:
        # Extract full text
        full_text = extract_text_from_pdf(pdf_path)
        if not full_text:
            logger.warning(f"No text extracted from {pdf_path}")
            return "", []
        
        # Extract pages
        pages = extract_pages_from_pdf(pdf_path)
        if not pages:
            logger.warning(f"No pages extracted from {pdf_path}")
            return full_text, []
        
        # Process pages into structured format
        pages_data = []
        for i, page_text in enumerate(pages):
            if not page_text.strip():
                logger.debug(f"Skipping empty page {i+1}")
                continue
            
            # Calculate medical confidence
            medical_confidence = measure_medical_confidence(page_text)
            
            # Extract medical terms for additional metadata
            medical_terms = extract_medical_terms(page_text)
            
            # Calculate page hash
            page_hash = hash_text(page_text)
            
            # Create page entry
            page_data = {
                "page_idx": i,
                "text": page_text,
                "text_snippet": page_text[:300].replace("\n", " ").strip(),
                "page_hash": page_hash,
                "medical_confidence": medical_confidence,
                "medical_terms": medical_terms,
                "duplicate_confidence": 0.0  # Will be populated during duplicate analysis
            }
            
            pages_data.append(page_data)
        
        logger.debug(f"Extracted {len(pages_data)} pages from {pdf_path}")
        return full_text, pages_data
        
    except Exception as e:
        logger.error(f"Error extracting text from {pdf_path}: {e}", exc_info=True)
        raise


def analyze_document_content(pdf_path: str) -> Dict[str, Any]:
    """
    Perform a comprehensive content analysis of a document.
    Includes text extraction, medical content detection, and duplicate analysis.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        Dictionary with analysis results
        
    Raises:
        Exception: If analysis fails
    """
    logger.debug(f"Analyzing document content for {pdf_path}")
    
    try:
        # Extract full text
        full_text = extract_text_from_pdf(pdf_path)
        if not full_text:
            logger.warning(f"No text extracted from {pdf_path}")
            return {
                "error": "No text extracted",
                "is_medical": False,
                "medical_confidence": 0.0,
                "duplicate_confidence": 0.0,
                "hash": None,
                "tfidf_vector": None
            }
        
        # Extract pages
        pages = extract_pages_from_pdf(pdf_path)
        
        # Calculate medical confidence
        medical_confidences = [measure_medical_confidence(page) for page in pages if page.strip()]
        avg_medical_confidence = sum(medical_confidences) / len(medical_confidences) if medical_confidences else 0.0
        
        # Compute document hash and TF-IDF vector
        doc_hash = compute_document_hash(pdf_path)
        tfidf_vec = compute_document_tfidf_vector(pdf_path)
        
        # Determine if document is medical
        is_medical = avg_medical_confidence > 0.6
        
        return {
            "is_medical": is_medical,
            "medical_confidence": avg_medical_confidence,
            "duplicate_confidence": 0.0,  # Will be populated by the caller
            "hash": doc_hash,
            "tfidf_vector": tfidf_vec,
            "page_count": len(pages),
            "medical_pages": sum(1 for conf in medical_confidences if conf > 0.6)
        }
        
    except Exception as e:
        logger.error(f"Error analyzing document content for {pdf_path}: {e}", exc_info=True)
        raise


def extract_metadata(pdf_path: str) -> Dict[str, Any]:
    """
    Extract metadata from a PDF file.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        Dictionary with metadata
        
    Raises:
        Exception: If extraction fails
    """
    try:
        import fitz  # PyMuPDF
        
        doc = fitz.open(pdf_path)
        metadata = doc.metadata
        
        # Add some additional metadata
        metadata["page_count"] = len(doc)
        metadata["file_size"] = os.path.getsize(pdf_path)
        metadata["is_encrypted"] = doc.is_encrypted
        
        # Extract form fields if present
        metadata["has_form_fields"] = len(doc.get_form_text_fields()) > 0
        
        # Get creation and modification dates
        metadata["created_at"] = metadata.get("creationDate", "")
        metadata["modified_at"] = metadata.get("modDate", "")
        
        doc.close()
        
        return metadata
        
    except Exception as e:
        logger.error(f"Error extracting metadata from {pdf_path}: {e}", exc_info=True)
        raise