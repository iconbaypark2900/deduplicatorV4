"""
Service for performing medical content analysis on documents.
"""
import logging
from typing import List, Dict, Optional, Any

from sqlalchemy.orm import Session
from utils.database import DocumentMetadata, Page, MedicalEntity, get_document_metadata_by_id, get_pages_by_document_id, create_user # Assuming create_user is placeholder, we need a way to add MedicalEntity
from ingestion.preprocessing import measure_medical_confidence, extract_medical_terms

# Configure logging
logger = logging.getLogger(__name__)

# Helper functions (originally from data_science.py)

def detect_specialty(text: str, medical_terms: List[str]) -> Optional[str]:
    """
    Attempt to detect medical specialty based on text and terms.
    This is a simple heuristic approach.
    
    Args:
        text: Page text
        medical_terms: List of medical terms
        
    Returns:
        Detected specialty or None
    """
    # Define specialty keywords
    specialties = {
        "cardiology": ["heart", "cardiac", "ecg", "ekg", "coronary", "arrhythmia", "myocardial"],
        "neurology": ["brain", "neural", "neuro", "seizure", "epilepsy", "cognitive"],
        "oncology": ["cancer", "tumor", "oncology", "malignant", "chemotherapy", "radiation"],
        "orthopedics": ["bone", "joint", "fracture", "orthopedic", "musculoskeletal"],
        "pediatrics": ["child", "pediatric", "infant", "adolescent"],
        "radiology": ["imaging", "ct scan", "mri", "xray", "x-ray", "radiograph"]
    }
    
    # Count specialty term occurrences
    specialty_counts = {specialty: 0 for specialty in specialties}
    
    # Check text
    text_lower = text.lower()
    for specialty, keywords in specialties.items():
        for keyword in keywords:
            if keyword in text_lower:
                specialty_counts[specialty] += 1
    
    # Check medical terms
    for term in medical_terms:
        term_lower = term.lower()
        for specialty, keywords in specialties.items():
            for keyword in keywords:
                if keyword in term_lower:
                    specialty_counts[specialty] += 1
    
    # Find specialty with highest count
    max_count = 0
    max_specialty = None
    
    for specialty, count in specialty_counts.items():
        if count > max_count:
            max_count = count
            max_specialty = specialty
    
    # Only return specialty if sufficient evidence
    return max_specialty if max_count >= 2 else None


def determine_document_specialty(pages_analysis: List[Dict[str, Any]]) -> Optional[str]:
    """
    Determine the overall document specialty based on page specialties.
    
    Args:
        pages_analysis: List of page analysis data (each dict should have a "specialty" key)
        
    Returns:
        Overall document specialty or None
    """
    # Count specialty occurrences
    specialty_counts = {}
    
    for page in pages_analysis:
        specialty = page.get("specialty")
        if specialty:
            if specialty in specialty_counts:
                specialty_counts[specialty] += 1
            else:
                specialty_counts[specialty] = 1
    
    # Find specialty with highest count
    max_count = 0
    max_specialty = None
    
    for specialty, count in specialty_counts.items():
        if count > max_count:
            max_count = count
            max_specialty = specialty
    
    return max_specialty

def analyze_document_medical_content(db: Session, doc_id: str) -> Dict[str, Any]:
    """
    Performs medical content analysis on a specified document already in the database.
    Updates database with findings (e.g., page medical confidence, medical entities).

    Args:
        db: SQLAlchemy session.
        doc_id: The ID of the document to analyze.

    Returns:
        A dictionary summarizing the medical analysis of the document.
    
    Raises:
        ValueError: If the document with the given doc_id is not found.
    """
    logger.info(f"Starting medical content analysis for document ID: {doc_id}")
    doc_meta = get_document_metadata_by_id(db, doc_id)
    if not doc_meta:
        logger.error(f"Document with ID {doc_id} not found for medical analysis.")
        raise ValueError(f"Document with ID {doc_id} not found.")

    db_pages = get_pages_by_document_id(db, doc_id)
    if not db_pages:
        logger.warning(f"No pages found for document ID {doc_id}. Returning empty analysis.")
        return {
            "doc_id": doc_id,
            "filename": doc_meta.filename,
            "overall_specialty": None,
            "total_pages_analyzed": 0,
            "medical_pages_count": 0,
            "average_medical_confidence": 0.0,
            "pages_analysis": []
        }

    pages_analysis_results = []
    total_medical_confidence = 0.0
    medical_pages_count = 0

    for page_obj in db_pages:
        page_text = page_obj.text_snippet # Assuming text_snippet is sufficient.
                                        # If full text is required, it needs to be fetched/ensured.
        if not page_text:
            logger.debug(f"Page {page_obj.page_number} of doc {doc_id} has no text. Skipping medical analysis for this page.")
            pages_analysis_results.append({
                "page_num": page_obj.page_number,
                "is_medical": False,
                "medical_confidence": 0.0,
                "specialty": None,
                "terms_count": 0,
                "extracted_terms": []
            })
            continue

        page_medical_confidence = measure_medical_confidence(page_text)
        page_medical_terms = extract_medical_terms(page_text)
        page_specialty = detect_specialty(page_text, page_medical_terms)

        # Update Page object in DB
        page_obj.medical_confidence = page_medical_confidence
        # Potentially add other fields like page_obj.specialty = page_specialty if model supports it
        db.add(page_obj)

        # Create MedicalEntity objects in DB
        for term_text in page_medical_terms:
            # Basic check to avoid overly long "terms" or duplicates if necessary
            if len(term_text) > 255: # Max length of MedicalEntity.entity_value
                logger.warning(f"Medical term \"{term_text[:50]}...\" too long for page {page_obj.id}, doc {doc_id}. Skipping term.")
                continue
            
            # Check if entity already exists for this page to avoid duplicates (optional, depends on desired behavior)
            existing_entity = db.query(MedicalEntity).filter_by(page_id=page_obj.id, entity_type="medical_term", entity_value=term_text).first()
            if not existing_entity:
                medical_entity = MedicalEntity(
                    document_id=doc_id,
                    page_id=page_obj.id,
                    entity_type="medical_term", # Or more specific if classification is done
                    entity_value=term_text,
                    confidence=None # Confidence for the term itself, if available from extract_medical_terms
                )
                db.add(medical_entity)
        
        is_medical_page = page_medical_confidence > 0.6 # Example threshold
        if is_medical_page:
            medical_pages_count += 1
        total_medical_confidence += page_medical_confidence

        pages_analysis_results.append({
            "page_num": page_obj.page_number,
            "is_medical": is_medical_page,
            "medical_confidence": page_medical_confidence,
            "specialty": page_specialty,
            "terms_count": len(page_medical_terms),
            "extracted_terms": page_medical_terms[:20] # Sample of terms
        })

    overall_doc_specialty = determine_document_specialty(pages_analysis_results)
    average_confidence = total_medical_confidence / len(db_pages) if db_pages else 0.0

    # Update DocumentMetadata (if fields exist, e.g., overall_specialty, avg_medical_confidence)
    # For now, we are not adding new fields to DocumentMetadata in this step.
    # doc_meta.overall_specialty = overall_doc_specialty (Example)
    # db.add(doc_meta)

    try:
        db.commit()
        logger.info(f"Successfully completed medical analysis and updated DB for document ID: {doc_id}")
    except Exception as e:
        db.rollback()
        logger.error(f"DB commit failed after medical analysis for doc {doc_id}: {e}", exc_info=True)
        # Decide if to raise an error or return partial/non-persisted results
        # For now, we'll indicate that the DB update might have failed in the response or log heavily.
        # Re-raising an error might be cleaner for the caller to handle.
        raise Exception(f"Database update failed during medical analysis for doc {doc_id}: {str(e)}")

    return {
        "doc_id": doc_id,
        "filename": doc_meta.filename,
        "overall_specialty": overall_doc_specialty,
        "total_pages_analyzed": len(db_pages),
        "medical_pages_count": medical_pages_count,
        "average_medical_confidence": round(average_confidence, 4),
        "pages_analysis": pages_analysis_results
    }

# More service functions will be added here to orchestrate analysis for DB documents. 