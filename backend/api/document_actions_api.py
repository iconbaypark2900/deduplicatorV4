"""
API endpoints for performing actions and retrieving analysis for documents stored in the database.
"""
import logging
from fastapi import APIRouter, HTTPException, Depends, Path
from sqlalchemy.orm import Session
from typing import Dict, Any

from utils.database import get_db
from backend.services.medical_analyzer_service import analyze_document_medical_content
# We will need a Pydantic model for the response of the medical analysis
from backend.models.schemas import DocumentMedicalAnalysisResponse # UPDATED

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/documents", tags=["Document Actions & Analysis"])

# Placeholder for a Pydantic response model - define this in schemas.py later
# For now, we'll use a general Dict[str, Any] response

@router.post("/{doc_id}/medical-analysis", response_model=DocumentMedicalAnalysisResponse) # UPDATED
async def trigger_document_medical_analysis(
    doc_id: str = Path(..., title="The ID of the document to analyze"), 
    db: Session = Depends(get_db)
):
    """
    Triggers medical content analysis for a specified document. 
    The analysis results (e.g., page medical confidence, extracted medical entities) 
    are stored in the database.
    """
    try:
        logger.info(f"Received request to trigger medical analysis for doc_id: {doc_id}")
        analysis_summary = analyze_document_medical_content(db=db, doc_id=doc_id)
        return analysis_summary
    except ValueError as ve:
        logger.warning(f"Value error during medical analysis for doc_id {doc_id}: {str(ve)}")
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error(f"Failed to trigger medical analysis for doc_id {doc_id}: {str(e)}", exc_info=True)
        # The service function already handles rollback on DB error during its commit attempt.
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during medical analysis: {str(e)}")

@router.get("/{doc_id}/medical-analysis", response_model=DocumentMedicalAnalysisResponse) # UPDATED
async def get_document_medical_analysis_results(
    doc_id: str = Path(..., title="The ID of the document to retrieve analysis for"),
    db: Session = Depends(get_db)
):
    """
    Retrieves (or re-calculates) the medical content analysis for a specified document.
    Note: Currently, this re-runs the analysis. For pre-computed results, 
    the service and storage mechanism would need to be adapted.
    """
    try:
        logger.info(f"Received request to get medical analysis for doc_id: {doc_id}")
        # For now, this re-runs the analysis. If analysis is computationally expensive 
        # and results are stable post-analysis, consider storing the summary 
        # or parts of it in DocumentMetadata or a dedicated AnalysisResults table.
        analysis_summary = analyze_document_medical_content(db=db, doc_id=doc_id)
        return analysis_summary
    except ValueError as ve:
        logger.warning(f"Value error retrieving medical analysis for doc_id {doc_id}: {str(ve)}")
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error(f"Failed to retrieve medical analysis for doc_id {doc_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred while retrieving medical analysis: {str(e)}") 