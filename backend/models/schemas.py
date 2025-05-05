"""
Pydantic schemas for API request/response models.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum


class ReviewStatus(str, Enum):
    """Possible review statuses for documents."""
    PENDING = "pending"
    KEEP = "keep"
    ARCHIVE = "archive"


class ReviewDecision(str, Enum):
    """Possible reviewer decisions for pages."""
    DUPLICATE = "duplicate"
    UNIQUE = "unique"
    UNSURE = "unsure"


class PageMetadata(BaseModel):
    """
    Metadata for a single page.
    """
    page_num: int
    page_hash: str
    text_snippet: str
    decision: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[str] = None
    filename: Optional[str] = None
    doc_id: Optional[str] = None


class MatchDetails(BaseModel):
    """
    Details about a matching document.
    """
    matched_doc: str
    similarity: float


class DuplicatePair(BaseModel):
    """
    A pair of duplicate pages.
    """
    page1_idx: int
    page2_idx: int
    similarity: float


class UploadResponse(BaseModel):
    """
    Response returned after document upload and analysis.
    """
    doc_id: str
    status: str  # 'unique' or 'duplicate'
    match: Optional[MatchDetails] = None
    pages: List[PageMetadata]
    duplicates: List[DuplicatePair] = []


class ReviewRequest(BaseModel):
    """
    Payload sent when a reviewer makes a decision.
    """
    doc_id: str
    decision: str  # e.g., 'duplicate', 'unique', 'unsure'
    reviewer: str
    notes: Optional[str] = ""
    pages: List[str]  # List of page hashes


class DocumentStatusUpdate(BaseModel):
    """
    Payload for updating a document's status (keep/archive).
    """
    documentId: str
    action: ReviewStatus
    reviewer: str
    notes: Optional[str] = None


class RebuildRequest(BaseModel):
    """
    Request to rebuild a document from selected pages.
    """
    filename: str
    pages: List[str]  # List of page hashes


class PageInfo(BaseModel):
    """
    Information about a page in a document.
    """
    hash: str
    index: int
    text_snippet: str
    medical_confidence: Optional[float] = None
    duplicate_confidence: Optional[float] = None


class DocumentAnalysis(BaseModel):
    """
    Analysis information for a document.
    """
    doc_id: str
    filename: str
    status: str
    pages: List[PageInfo]
    duplicates: List[DuplicatePair]
    lastReviewer: Optional[str] = None
    lastReviewedAt: Optional[str] = None
    reviewHistory: Optional[List[Dict[str, Any]]] = None


class PageResponse(BaseModel):
    """
    Response model for page data with confidence scores
    """
    page_hash: str
    page_num: int
    status: str
    image_path: Optional[str] = None
    text_snippet: str
    filename: str
    medical_confidence: float = 0.0
    duplicate_confidence: float = 0.0


class ReviewHistoryEntry(BaseModel):
    """
    Entry in a document's review history.
    """
    status: str
    decision: str
    reviewer: str
    timestamp: str
    notes: Optional[str] = None


class BatchAnalysisResult(BaseModel):
    """
    Result of batch folder analysis.
    """
    file1: str
    file2: str
    type: str  # 'exact_duplicate' or 'near_duplicate'
    similarity: Optional[float] = None


class BatchAnalysisResponse(BaseModel):
    """
    Response from batch folder analysis.
    """
    total_documents: int
    duplicates_found: int
    results: List[BatchAnalysisResult]


class ComparisonResult(BaseModel):
    """
    Result of document-to-document comparison.
    """
    document_similarity: float
    is_high_similarity: bool
    similar_pages: List[Dict[str, Any]]


class PageMetadataResponse(BaseModel):
    """
    Response with page metadata.
    """
    page_hash: str
    page_num: int
    filename: str
    doc_id: str
    pdf_path: Optional[str] = None


class PageSimilarityQuery(BaseModel):
    """
    Query for finding similar pages.
    """
    text: str
    threshold: float = 0.85
    max_results: int = 10