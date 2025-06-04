"""
Data science API endpoints.
Provides routes for medical content analysis, document clustering, and topic modeling.
"""

import os
import uuid
import logging
from fastapi import APIRouter, UploadFile, File, HTTPException, Form, Body
from fastapi.responses import FileResponse, JSONResponse
from typing import List, Dict, Optional, Any
import tempfile

from backend.services.extractor import extract_text_and_pages, analyze_document_content
from ingestion.preprocessing import measure_medical_confidence, extract_medical_terms
from utils.config import settings
from backend.services.medical_analyzer_service import detect_specialty, determine_document_specialty

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/data-science", tags=["Data Science"])


@router.post("/medical")
async def analyze_medical_content(file: UploadFile = File(...)):
    """
    Analyze a document for medical content.
    
    Args:
        file: PDF file to analyze
        
    Returns:
        Medical content analysis results
        
    Raises:
        HTTPException: If analysis fails
    """
    try:
        # Save uploaded file temporarily
        temp_path = f"storage/tmp/{uuid.uuid4()}_{file.filename}"
        os.makedirs(os.path.dirname(temp_path), exist_ok=True)
        
        with open(temp_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # Extract document content
        full_text, pages_data = extract_text_and_pages(temp_path)
        
        # Check if text extraction was successful
        if not full_text:
            raise HTTPException(status_code=400, detail="Could not extract text from document")
        
        # Analyze document
        doc_analysis = analyze_document_content(temp_path)
        
        # Analyze pages for medical content
        pages_analysis = []
        medical_pages = 0
        
        for i, page in enumerate(pages_data):
            page_text = page.get("text", "")
            medical_confidence = page.get("medical_confidence", 0.0)
            medical_terms = page.get("medical_terms", [])
            
            # Determine if page is medical
            is_medical = medical_confidence > 0.6
            if is_medical:
                medical_pages += 1
            
            # Add page analysis
            pages_analysis.append({
                "page_num": i + 1,
                "is_medical": is_medical,
                "confidence": medical_confidence,
                "specialty": detect_specialty(page_text, medical_terms) if is_medical else None,
                "term_ratio": len(medical_terms) / len(page_text.split()) if page_text else 0,
                "terms": medical_terms[:20] if len(medical_terms) > 0 else None
            })
        
        # Determine the overall specialty
        overall_specialty = determine_document_specialty(pages_analysis)
        
        # Calculate medical page ratio
        medical_page_ratio = medical_pages / len(pages_data) if pages_data else 0
        
        # Create response
        result = {
            "document_id": str(uuid.uuid4()),
            "filename": file.filename,
            "is_medical": doc_analysis.get("is_medical", False),
            "confidence": doc_analysis.get("medical_confidence", 0.0),
            "specialty": overall_specialty,
            "medical_page_ratio": medical_page_ratio,
            "pages": pages_analysis
        }
        
        # Clean up
        try:
            os.unlink(temp_path)
        except:
            pass
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Medical analysis failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Medical analysis failed: {str(e)}")


@router.post("/content")
async def analyze_content(files: List[UploadFile] = File(...)):
    """
    Analyze document content for topics, entities, and structure.
    
    Args:
        files: List of PDF files to analyze
        
    Returns:
        Content analysis results
        
    Raises:
        HTTPException: If analysis fails
    """
    try:
        # Check if files were uploaded
        if not files:
            raise HTTPException(status_code=400, detail="No files uploaded")
        
        # Save uploaded files temporarily
        temp_paths = []
        
        for file in files:
            temp_path = f"storage/tmp/{uuid.uuid4()}_{file.filename}"
            os.makedirs(os.path.dirname(temp_path), exist_ok=True)
            
            with open(temp_path, "wb") as f:
                content = await file.read()
                f.write(content)
                
            temp_paths.append(temp_path)
        
        # Process documents
        all_texts = []
        all_terms = []
        section_counts = {}
        avg_word_count = 0
        
        for temp_path in temp_paths:
            # Extract document content
            full_text, pages_data = extract_text_and_pages(temp_path)
            
            # Skip if text extraction failed
            if not full_text:
                continue
                
            all_texts.append(full_text)
            
            # Count words
            word_count = len(full_text.split())
            avg_word_count += word_count
            
            # Extract medical terms
            terms = extract_medical_terms(full_text)
            all_terms.extend(terms)
            
            # Detect sections
            from ingestion.preprocessing import detect_section_headers
            sections = detect_section_headers(full_text)
            
            for section in sections:
                section_name = section["section"].lower()
                if section_name in section_counts:
                    section_counts[section_name] += 1
                else:
                    section_counts[section_name] = 1
        
        # Calculate average word count
        avg_word_count = avg_word_count / len(all_texts) if all_texts else 0
        
        # Extract topics using a simple TF-IDF approach
        topics = []
        if all_texts:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.decomposition import NMF
            
            # Number of topics to extract
            n_topics = min(5, len(all_texts))
            
            if n_topics > 1:
                # Create TF-IDF representation
                vectorizer = TfidfVectorizer(max_features=1000, stop_words='english')
                tfidf = vectorizer.fit_transform(all_texts)
                
                # Extract topics
                nmf = NMF(n_components=n_topics, random_state=42)
                nmf.fit(tfidf)
                
                # Get feature names
                feature_names = vectorizer.get_feature_names_out()
                
                # Create topics
                for topic_idx, topic in enumerate(nmf.components_):
                    top_words = [feature_names[i] for i in topic.argsort()[:-11:-1]]
                    topics.append({
                        "topic_id": topic_idx,
                        "words": top_words,
                        "weight": float(topic.sum() / topic.size)
                    })
        
        # Process medical terms
        term_counts = {}
        medication_counts = {}
        condition_counts = {}
        procedure_counts = {}
        
        for term in all_terms:
            term_lower = term.lower()
            
            # Count general medical terms
            if term_lower in term_counts:
                term_counts[term_lower] += 1
            else:
                term_counts[term_lower] = 1
            
            # Attempt to categorize term
            if term_lower.endswith(('mg', 'mcg', 'ml', 'g')):
                # Likely a medication
                if term_lower in medication_counts:
                    medication_counts[term_lower] += 1
                else:
                    medication_counts[term_lower] = 1
            elif any(suffix in term_lower for suffix in ('itis', 'osis', 'emia')):
                # Likely a condition
                if term_lower in condition_counts:
                    condition_counts[term_lower] += 1
                else:
                    condition_counts[term_lower] = 1
            elif any(suffix in term_lower for suffix in ('ectomy', 'otomy', 'plasty', 'scopy')):
                # Likely a procedure
                if term_lower in procedure_counts:
                    procedure_counts[term_lower] += 1
                else:
                    procedure_counts[term_lower] = 1
        
        # Format section data
        sections_data = []
        for section_name, count in section_counts.items():
            sections_data.append({
                "name": section_name,
                "count": count
            })
        
        # Sort sections by frequency
        sections_data.sort(key=lambda x: x["count"], reverse=True)
        
        # Format term data
        def format_term_counts(counts_dict):
            return [{"term": term, "count": count} for term, count in sorted(counts_dict.items(), key=lambda x: x[1], reverse=True)]
        
        medical_terms = format_term_counts(term_counts)
        medications = format_term_counts(medication_counts)
        conditions = format_term_counts(condition_counts)
        procedures = format_term_counts(procedure_counts)
        
        # Create response
        result = {
            "document_id": str(uuid.uuid4()),
            "filename": files[0].filename if len(files) == 1 else None,
            "total_documents": len(all_texts),
            "topics": topics,
            "sections": sections_data,
            "medical_terms": medical_terms[:50],
            "medications": medications[:30],
            "conditions": conditions[:30],
            "procedures": procedures[:30],
            "average_document_length": avg_word_count,
            "average_word_count": avg_word_count
        }
        
        # Clean up
        for temp_path in temp_paths:
            try:
                os.unlink(temp_path)
            except:
                pass
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Content analysis failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Content analysis failed: {str(e)}")


# Helper functions
# calculate_node_positions function has been moved to backend.services.clustering_service