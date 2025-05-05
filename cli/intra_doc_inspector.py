#!/usr/bin/env python3
"""
Intra-document duplicate inspector CLI.
Analyzes a single document for internal duplicate pages.
"""

import os
import sys
import argparse
import json
import logging
from typing import Optional, List, Dict
from datetime import datetime

from backend.services.deduplicator import DuplicateService
from ingestion.pdf_reader import extract_pages_from_pdf
from utils.duplicate_analysis import analyze_document_pages

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def inspect_intra_document(pdf_path: str, threshold: float = 0.85, output_path: Optional[str] = None) -> int:
    """
    Analyze a single document for internal duplicate pages.
    
    Args:
        pdf_path: Path to PDF file
        threshold: Similarity threshold (0-1)
        output_path: Path to save results
        
    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    logger.info("=== Intra-Document Duplicate Inspector ===")
    logger.info(f"Analyzing: {os.path.basename(pdf_path)}")
    
    try:
        # Create deduplication service
        service = DuplicateService()
        
        # Extract pages
        pages = extract_pages_from_pdf(pdf_path)
        if not pages:
            logger.error("Could not extract pages from the document.")
            return 1
        
        logger.info(f"Extracted {len(pages)} pages from document")
        
        # Analyze similarities between pages
        similar_pairs = analyze_document_pages(pages, threshold=threshold)
        
        # Format results
        results = []
        for pair in similar_pairs:
            page1_idx = pair["page1_idx"]
            page2_idx = pair["page2_idx"]
            similarity = pair["similarity"]
            
            results.append({
                "page1": page1_idx + 1,  # Convert to 1-indexed
                "page2": page2_idx + 1,  # Convert to 1-indexed
                "similarity": similarity
            })
        
        # Output results
        if not results:
            print("\n✅ No duplicate pages detected in the document.")
        else:
            print(f"\n⚠️  Found {len(results)} pairs of similar pages:")
            
            for result in results:
                print(f"  - Page {result['page1']} is similar to Page {result['page2']} (similarity: {result['similarity']:.3f})")
        
        # Save results to file if output path provided
        if output_path:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            with open(output_path, 'w') as f:
                json.dump({
                    "timestamp": datetime.now().isoformat(),
                    "document": os.path.basename(pdf_path),
                    "total_pages": len(pages),
                    "duplicate_pairs": len(results),
                    "results": results
                }, f, indent=2)
                
            print(f"\nResults saved to: {output_path}")
        
        return 0
        
    except Exception as e:
        logger.error(f"Error analyzing document: {e}", exc_info=True)
        return 1


def main() -> int:
    """
    Main entry point for the intra-document analysis CLI.
    
    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    parser = argparse.ArgumentParser(
        description="Analyze a single document for internal duplicate pages."
    )
    parser.add_argument("document", help="PDF document to analyze")
    parser.add_argument("--threshold", type=float, default=0.85,
                       help="Similarity threshold (0-1)")
    parser.add_argument("--output", help="Output file for results (JSON)")
    
    if len(sys.argv) < 2:
        parser.print_help()
        return 1
    
    args = parser.parse_args()
    
    if not os.path.isfile(args.document):
        logger.error(f"Document not found: {args.document}")
        return 1
    
    if not args.document.lower().endswith('.pdf'):
        logger.error("Only PDF files are supported")
        return 1
    
    return inspect_intra_document(args.document, args.threshold, args.output)


if __name__ == "__main__":
    sys.exit(main())