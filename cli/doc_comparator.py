#!/usr/bin/env python3
"""
Document-to-document comparison CLI.
Compares two PDF documents and reports similarity metrics.
"""

import sys
import os
import argparse
import logging
from tabulate import tabulate
from typing import Optional, Tuple, List

from similarity.engine import SimilarityEngine
from utils.duplicate_analysis import analyze_document_similarity
from ingestion.pdf_reader import extract_pages_from_pdf, extract_text_from_pdf
from similarity.tfidf import analyze_document_pages

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def compare_documents_workflow(file1: str, file2: str, threshold: float = 0.85) -> int:
    """
    Compare two documents and report similarity metrics.
    
    Args:
        file1: Path to first PDF file
        file2: Path to second PDF file
        threshold: Similarity threshold (0-1)
        
    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    logger.info("=== Document-to-Document Comparator ===")
    logger.info(f"Comparing: {file1} <-> {file2}")
    
    try:
        # Extract text from both documents
        text1 = extract_text_from_pdf(file1)
        text2 = extract_text_from_pdf(file2)
        
        if not text1 or not text2:
            logger.error("Could not extract text from one or both documents.")
            return 1
        
        # Compare document-level similarity
        engine = SimilarityEngine()
        doc1_vector = engine.vectorize(text1)
        doc2_vector = engine.vectorize(text2)
        doc_similarity = engine.compute_similarity(doc1_vector, doc2_vector)
        
        print(f"\nDocument-level similarity: {doc_similarity:.3f}")
        if doc_similarity > threshold:
            print("⚠️  Warning: High similarity detected at document level!")
        else:
            print("✅ Documents appear distinct at the document level.")
        
        # Compare pages for more detailed analysis
        doc1_pages = extract_pages_from_pdf(file1)
        doc2_pages = extract_pages_from_pdf(file2)
        
        if not doc1_pages or not doc2_pages:
            logger.error("Could not extract pages from one or both documents.")
            return 1
        
        # Analyze page-to-page similarity
        print("\nPage-to-Page Similarity Analysis:")
        
        # Create a matrix of page similarities
        similarity_matrix = []
        similar_pages = []
        
        for i, page1 in enumerate(doc1_pages):
            row = []
            for j, page2 in enumerate(doc2_pages):
                if not page1.strip() or not page2.strip():
                    row.append(0.0)
                    continue
                
                vector1 = engine.vectorize(page1)
                vector2 = engine.vectorize(page2)
                sim = engine.compute_similarity(vector1, vector2)
                row.append(sim)
                
                if sim > threshold:
                    similar_pages.append((i+1, j+1, sim))
                    print(f" - Document 1 page {i+1} is similar to Document 2 page {j+1} (similarity: {sim:.3f})")
            
            similarity_matrix.append(row)
        
        # Print similarity matrix if it's not too large
        if len(doc1_pages) <= 10 and len(doc2_pages) <= 10:
            print("\nSimilarity Matrix:")
            headers = [""] + [f"Doc2 P{j+1}" for j in range(len(doc2_pages))]
            table_data = [[f"Doc1 P{i+1}"] + [f"{sim:.3f}" for sim in row] for i, row in enumerate(similarity_matrix)]
            print(tabulate(table_data, headers=headers, tablefmt="grid"))
        
        if not similar_pages:
            print("\n✅ No highly similar pages found between the documents.")
        else:
            print(f"\n⚠️  Found {len(similar_pages)} pairs of similar pages.")
        
        return 0
        
    except Exception as e:
        logger.error(f"Error comparing documents: {e}", exc_info=True)
        return 1


def main() -> int:
    """
    Main entry point for the document comparison CLI.
    
    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    parser = argparse.ArgumentParser(description="Compare two PDF documents for similarity.")
    parser.add_argument("file1", help="First PDF file")
    parser.add_argument("file2", help="Second PDF file")
    parser.add_argument("--threshold", type=float, default=0.85,
                       help="Similarity threshold (0-1)")
    
    if len(sys.argv) < 3:
        parser.print_help()
        return 1
    
    args = parser.parse_args()
    
    if not os.path.isfile(args.file1):
        logger.error(f"File not found: {args.file1}")
        return 1
    
    if not os.path.isfile(args.file2):
        logger.error(f"File not found: {args.file2}")
        return 1
    
    return compare_documents_workflow(args.file1, args.file2, args.threshold)


if __name__ == "__main__":
    sys.exit(main())