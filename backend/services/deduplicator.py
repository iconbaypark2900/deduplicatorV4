"""
Core deduplication service for medical document processing.
Provides methods for detecting exact and near-duplicate documents and pages.
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, Any
import os
import json
import logging

from similarity.engine import SimilarityEngine
from similarity.hashing import compute_document_hash, get_minhash
from ingestion.pdf_reader import extract_text_from_pdf, extract_pages_from_pdf
from utils.config import settings
from utils.duplicate_analysis import analyze_document_pages

# Configure logging
logger = logging.getLogger(__name__)

# Constants
DOC_SIMILARITY_THRESHOLD = settings.DOC_SIMILARITY_THRESHOLD
PAGE_SIMILARITY_THRESHOLD = settings.PAGE_SIMILARITY_THRESHOLD
MIN_SIMILAR_PAGES = settings.MIN_SIMILAR_PAGES


class DuplicateService:
    """
    Main service for detecting duplicates across PDFs.
    Handles both exact and approximate matching.
    """

    def __init__(self):
        """Initialize the duplicate detection service."""
        self.engine = SimilarityEngine()
        self.hash_log_path = "storage/metadata/hash_set.json"
        
        # Ensure storage directories exist
        os.makedirs("storage/metadata", exist_ok=True)
        os.makedirs("storage/documents/unique", exist_ok=True)
        os.makedirs("storage/documents/deduplicated", exist_ok=True)
        os.makedirs("storage/documents/flagged_for_review", exist_ok=True)

    def _load_hash_log(self) -> set:
        """Load previously seen document hashes."""
        if os.path.exists(self.hash_log_path):
            try:
                with open(self.hash_log_path, "r") as f:
                    content = f.read().strip()
                    return set(json.loads(content)) if content else set()
            except Exception as e:
                logger.error(f"Error loading hash log: {e}")
        return set()

    def _save_hash_log(self, hashes: set) -> None:
        """Save the updated hash log."""
        try:
            with open(self.hash_log_path, "w") as f:
                json.dump(list(hashes), f)
        except Exception as e:
            logger.error(f"Error saving hash log: {e}")

    def check_exact_duplicate(self, pdf_path: Union[str, Path]) -> bool:
        """
        Check if a document is an exact duplicate using SHA256 hash.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            bool: True if the document is an exact duplicate
        """
        doc_hash = compute_document_hash(str(pdf_path))
        if not doc_hash:
            return False
            
        seen_hashes = self._load_hash_log()
        return doc_hash in seen_hashes

    def add_to_hash_log(self, pdf_path: Union[str, Path]) -> Optional[str]:
        """
        Compute a document's hash and add it to the hash log.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            str: The computed hash, or None if extraction failed
        """
        doc_hash = compute_document_hash(str(pdf_path))
        if not doc_hash:
            return None
            
        seen_hashes = self._load_hash_log()
        seen_hashes.add(doc_hash)
        self._save_hash_log(seen_hashes)
        return doc_hash

    def find_match(self, text: str, threshold: float = 0.85) -> Dict[str, Optional[dict]]:
        """
        Determines whether the document is a duplicate using the unified similarity engine.

        Args:
            text (str): Raw or normalized full document text.
            threshold (float): Cosine similarity threshold for considering as duplicate.

        Returns:
            dict: {
                "status": "duplicate" or "unique",
                "details": {
                    "matched_doc": str,
                    "similarity": float
                } or None
            }
        """
        try:
            return self.engine.find_duplicate(text, threshold)
        except Exception as e:
            raise RuntimeError(f"Failed to compute match: {e}")

    def analyse_pair(self, file_a: Path, file_b: Path) -> Dict:
        """
        Compare two PDFs and return their document-level similarity
        plus any similar page pairs.
        
        Args:
            file_a: Path to the first PDF
            file_b: Path to the second PDF
            
        Returns:
            Dict containing similarity results
        """
        # Extract text from both documents
        doc1_text = extract_text_from_pdf(str(file_a))
        doc2_text = extract_text_from_pdf(str(file_b))
        
        if not doc1_text or not doc2_text:
            return {
                "doc_similarity": 0.0,
                "similar_pages": [],
                "error": "Failed to extract text from one or both documents"
            }
        
        # Compute document-level similarity
        doc1_vector = self.engine.vectorize(doc1_text)
        doc2_vector = self.engine.vectorize(doc2_text)
        doc_similarity = self.engine.compute_similarity(doc1_vector, doc2_vector)
        
        # Extract pages for page-level comparison
        doc1_pages = extract_pages_from_pdf(str(file_a))
        doc2_pages = extract_pages_from_pdf(str(file_b))
        
        if not doc1_pages or not doc2_pages:
            return {
                "doc_similarity": doc_similarity,
                "similar_pages": [],
                "error": "Failed to extract pages from one or both documents"
            }
        
        # Analyze page-level similarity
        page_vectors1 = self.engine.vectorize_batch(doc1_pages)
        page_vectors2 = self.engine.vectorize_batch(doc2_pages)
        
        similar_pages = []
        for i, vec1 in enumerate(page_vectors1):
            for j, vec2 in enumerate(page_vectors2):
                sim = self.engine.compute_similarity(vec1, vec2)
                if sim > PAGE_SIMILARITY_THRESHOLD:
                    similar_pages.append((i+1, j+1, float(sim)))
        
        return {
            "doc_similarity": float(doc_similarity),
            "similar_pages": similar_pages
        }

    def analyse_single(self, file_p: Path) -> List[Dict]:
        """
        Analyze one PDF for internal page duplicates and return results.
        
        Args:
            file_p: Path to the PDF file
            
        Returns:
            List of dictionaries with duplicate page information
        """
        # Extract pages
        pages = extract_pages_from_pdf(str(file_p))
        if not pages:
            return []
        
        # Analyze similarities between pages
        similar_pages = analyze_document_pages(pages, threshold=PAGE_SIMILARITY_THRESHOLD)
        return similar_pages

    def analyse_batch(self, paths: List[Path]) -> Dict[str, List[str]]:
        """
        Run duplicate detection across a batch of PDFs, returning
        a map of each file to its duplicates.
        
        Args:
            paths: List of paths to PDF files
            
        Returns:
            Dictionary mapping files to lists of duplicate files
        """
        results = {
            "exact_duplicates": [],
            "near_duplicates": []
        }
        
        # First pass: exact hash comparison
        hash_to_paths = {}
        for pdf_path in paths:
            doc_hash = compute_document_hash(str(pdf_path))
            if doc_hash:
                if doc_hash not in hash_to_paths:
                    hash_to_paths[doc_hash] = []
                hash_to_paths[doc_hash].append(str(pdf_path))
        
        # Identify exact duplicates
        for hash_val, paths_list in hash_to_paths.items():
            if len(paths_list) > 1:
                for i in range(len(paths_list)):
                    for j in range(i+1, len(paths_list)):
                        results["exact_duplicates"].append({
                            "file1": paths_list[i],
                            "file2": paths_list[j],
                            "type": "exact_duplicate"
                        })
        
        # Second pass: near-duplicate detection using vector similarity
        paths_to_vectors = {}
        for pdf_path in paths:
            text = extract_text_from_pdf(str(pdf_path))
            if text:
                vector = self.engine.vectorize(text)
                paths_to_vectors[str(pdf_path)] = vector
        
        # Compare vectors for near-duplicates
        paths_list = list(paths_to_vectors.keys())
        for i in range(len(paths_list)):
            for j in range(i+1, len(paths_list)):
                # Skip if already identified as exact duplicates
                is_exact = any(
                    (d["file1"] == paths_list[i] and d["file2"] == paths_list[j]) or
                    (d["file1"] == paths_list[j] and d["file2"] == paths_list[i])
                    for d in results["exact_duplicates"]
                )
                
                if not is_exact:
                    sim = self.engine.compute_similarity(
                        paths_to_vectors[paths_list[i]],
                        paths_to_vectors[paths_list[j]]
                    )
                    
                    if sim > DOC_SIMILARITY_THRESHOLD:
                        results["near_duplicates"].append({
                            "file1": paths_list[i],
                            "file2": paths_list[j],
                            "type": "near_duplicate",
                            "similarity": float(sim)
                        })
        
        # Combine results
        combined_results = results["exact_duplicates"] + results["near_duplicates"]
        return {
            "total_documents": len(paths),
            "duplicates_found": len(combined_results),
            "results": combined_results
        }