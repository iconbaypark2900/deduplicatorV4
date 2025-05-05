"""
Text preprocessing utilities for medical documents.
Provides functions for normalizing and sanitizing text from PDFs.
"""

import re
from typing import List, Dict, Set
import string
import logging

# Set up logging
logger = logging.getLogger(__name__)

# Common medical acronyms and abbreviations for reference
MEDICAL_ACRONYMS = {
    "BP": "blood pressure",
    "HR": "heart rate",
    "RR": "respiratory rate",
    "BMI": "body mass index",
    "MRI": "magnetic resonance imaging",
    "CT": "computed tomography",
    "ECG": "electrocardiogram",
    "EEG": "electroencephalogram",
    "ICU": "intensive care unit",
    # Add more as needed
}

# Common stopwords in medical documents
MEDICAL_STOPWORDS = {
    "patient", "doctor", "hospital", "clinic", "medical", "report",
    "date", "name", "id", "number", "mrn", "chart", "admission",
    "discharge", "page", "signature", "signed", "physician",
    "test", "result", "normal", "abnormal", "treatment", "procedure",
    "medication", "dose", "rx", "prescribed", "history", "present",
    "examination", "assessment", "plan", "follow", "up", "referral"
}


def normalize_medical_text(text: str) -> str:
    """
    Normalize medical text for more consistent comparisons.
    
    Args:
        text: Raw text from a medical document
        
    Returns:
        Normalized text
    """
    if not text:
        return ""
    
    # Convert to lowercase
    text = text.lower()
    
    # Replace common patterns
    text = text.replace("\n", " ")  # Replace newlines with spaces
    text = re.sub(r'\s+', ' ', text)  # Normalize whitespace
    
    # Remove headers, footers, and page numbers
    text = re.sub(r'page \d+ of \d+', '', text)
    text = re.sub(r'^\s*\d+\s*$', '', text, flags=re.MULTILINE)  # Standalone page numbers
    
    # Remove timestamps and dates
    text = re.sub(r'\d{1,2}:\d{2}(?::\d{2})?\s*(?:am|pm)?', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\d{1,2}[-/]\d{1,2}[-/]\d{2,4}', '', text)
    
    # Normalize or remove punctuation
    text = re.sub(r'[^\w\s-]', '', text)  # Remove punctuation except hyphens
    
    # Final cleanup
    text = text.strip()
    
    return text


def extract_medical_terms(text: str) -> List[str]:
    """
    Extract potential medical terms from document text.
    Uses pattern matching for common medical terminology patterns.
    
    Args:
        text: Text to extract terms from
        
    Returns:
        List of potential medical terms
    """
    if not text:
        return []
    
    terms = []
    
    # Look for terms that might be medical
    # Common patterns: dosages, measurements, diagnoses with ICD codes
    dosage_pattern = r'\d+\s*(?:mg|mcg|g|ml|cc|units|mEq)'
    terms.extend(re.findall(dosage_pattern, text, re.IGNORECASE))
    
    # Look for ICD codes
    icd_pattern = r'(?:ICD-\d+:|ICD-\d+)\s*([A-Z]\d+\.\d+)'
    terms.extend(re.findall(icd_pattern, text))
    
    # Look for common medical suffixes
    medical_suffix_pattern = r'\b\w+(?:itis|osis|emia|opathy|ectomy|otomy|plasty|scopy)\b'
    terms.extend(re.findall(medical_suffix_pattern, text, re.IGNORECASE))
    
    # Clean up and deduplicate
    terms = [term.strip() for term in terms]
    terms = list(set(terms))
    
    return terms


def detect_section_headers(text: str) -> List[Dict[str, str]]:
    """
    Detect and extract medical document section headers.
    
    Args:
        text: Document text
        
    Returns:
        List of dictionaries containing section names and their positions
    """
    # Common medical document section headers
    header_patterns = [
        r'(?:^|\n)(?:\d+\.\s*)?(?:chief\s+complaint|cc)(?:\s*:|\s*$)',
        r'(?:^|\n)(?:\d+\.\s*)?(?:history\s+of\s+present\s+illness|hpi)(?:\s*:|\s*$)',
        r'(?:^|\n)(?:\d+\.\s*)?(?:past\s+medical\s+history|pmh)(?:\s*:|\s*$)',
        r'(?:^|\n)(?:\d+\.\s*)?(?:medications|meds)(?:\s*:|\s*$)',
        r'(?:^|\n)(?:\d+\.\s*)?(?:allergies)(?:\s*:|\s*$)',
        r'(?:^|\n)(?:\d+\.\s*)?(?:family\s+history|fh)(?:\s*:|\s*$)',
        r'(?:^|\n)(?:\d+\.\s*)?(?:social\s+history|sh)(?:\s*:|\s*$)',
        r'(?:^|\n)(?:\d+\.\s*)?(?:review\s+of\s+systems|ros)(?:\s*:|\s*$)',
        r'(?:^|\n)(?:\d+\.\s*)?(?:physical\s+examination|pe)(?:\s*:|\s*$)',
        r'(?:^|\n)(?:\d+\.\s*)?(?:assessment)(?:\s*:|\s*$)',
        r'(?:^|\n)(?:\d+\.\s*)?(?:plan)(?:\s*:|\s*$)',
        r'(?:^|\n)(?:\d+\.\s*)?(?:impression)(?:\s*:|\s*$)',
        r'(?:^|\n)(?:\d+\.\s*)?(?:diagnosis|diagnoses)(?:\s*:|\s*$)',
        r'(?:^|\n)(?:\d+\.\s*)?(?:orders)(?:\s*:|\s*$)',
        r'(?:^|\n)(?:\d+\.\s*)?(?:follow\s*-?\s*up)(?:\s*:|\s*$)',
    ]
    
    headers = []
    for pattern in header_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        for match in matches:
            headers.append({
                "section": match.group().strip().strip(':').strip(),
                "position": match.start()
            })
    
    # Sort by position
    headers.sort(key=lambda x: x["position"])
    
    return headers


def measure_medical_confidence(text: str) -> float:
    """
    Measure the likelihood that a text is medical content.
    Returns a confidence score between 0 and 1.
    
    Args:
        text: Text to analyze
        
    Returns:
        Confidence score (0-1) that the text is medical content
    """
    if not text or len(text) < 50:
        return 0.0
    
    indicators = 0
    max_indicators = 5
    
    # Check for medical section headers
    sections = detect_section_headers(text)
    if len(sections) >= 2:
        indicators += 1
    
    # Check for medical terms
    terms = extract_medical_terms(text)
    if len(terms) >= 3:
        indicators += 1
    
    # Check for measurements and values
    if re.search(r'\d+\s*(?:mg|mcg|g|ml|cc|units|mEq|mmHg|cm|mm)', text, re.IGNORECASE):
        indicators += 1
    
    # Check for medical acronyms
    acronym_count = 0
    for acronym in MEDICAL_ACRONYMS.keys():
        if re.search(r'\b' + re.escape(acronym) + r'\b', text, re.IGNORECASE):
            acronym_count += 1
    
    if acronym_count >= 2:
        indicators += 1
    
    # Check for lab results pattern
    if re.search(r'(?:WBC|RBC|Hgb|Hct|MCV|PLT|Plt)[\s:]*\d+(?:\.\d+)?', text, re.IGNORECASE):
        indicators += 1
    
    # Calculate confidence score
    confidence = indicators / max_indicators
    
    return min(confidence, 1.0)  # Cap at 1.0