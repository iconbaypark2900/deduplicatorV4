#!/usr/bin/env python3
"""
Batch folder analysis CLI.
Analyzes a folder of PDFs to identify duplicates.
"""

import os
import sys
import argparse
import json
import logging
from typing import Optional, Dict, List
from datetime import datetime

from backend.services.deduplicator import DuplicateService
from utils.duplicate_analysis import (
    compute_document_hash,
    compute_document_tfidf_vector,
)
from similarity.engine import SimilarityEngine
from ingestion.pdf_reader import extract_text_from_pdf
from utils.config import settings

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def batch_folder_check(folder_path: str, threshold: float = 0.9, output_path: Optional[str] = None) -> int:
    """
    Analyze a folder of PDFs for duplicates.
    
    Args:
        folder_path: Path to folder containing PDFs
        threshold: Similarity threshold (0-1)
        output_path: Path to save results
        
    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    logger.info("=== Batch Folder Duplicate Checker ===")
    
    # Create deduplication service
    service = DuplicateService()
    
    # List all PDF files in the folder
    pdf_files = [os.path.join(folder_path, f) for f in os.listdir(folder_path) 
                if f.lower().endswith(".pdf")]
    
    if not pdf_files:
        logger.warning("No PDF files found in the folder.")
        return 1
    
    logger.info(f"Found {len(pdf_files)} PDF files. Processing...")
    
    # Track successfully processed files
    valid_files = []
    
    # First pass: exact duplicate detection
    exact_duplicates = []
    hash_to_files = {}
    
    for file in pdf_files:
        # Compute hash
        doc_hash = compute_document_hash(file)
        if doc_hash is None:
            logger.warning(f"Could not extract text from: {file}")
            continue
        
        valid_files.append(file)
        
        # Check for exact duplicates
        if doc_hash in hash_to_files:
            for existing_file in hash_to_files[doc_hash]:
                exact_duplicates.append({
                    "file1": os.path.basename(existing_file),
                    "file2": os.path.basename(file),
                    "type": "exact_duplicate"
                })
        
        # Add to hash mapping
        if doc_hash not in hash_to_files:
            hash_to_files[doc_hash] = []
        hash_to_files[doc_hash].append(file)
    
    # Second pass: near-duplicate detection
    near_duplicates = []
    
    # Group files by hash to avoid redundant comparisons
    unique_hashes = list(hash_to_files.keys())
    file_vectors = {}
    
    # Compute vectors for each unique hash
    for doc_hash in unique_hashes:
        file = hash_to_files[doc_hash][0]  # Take first file with this hash
        text = extract_text_from_pdf(file)
        if not text:
            continue
            
        vector = compute_document_tfidf_vector(file)
        if vector is None:
            logger.warning(f"Could not compute embedding for: {file}")
            continue
            
        file_vectors[doc_hash] = vector
    
    # Compare vectors
    engine = SimilarityEngine()
    for i in range(len(unique_hashes)):
        for j in range(i + 1, len(unique_hashes)):
            hash1 = unique_hashes[i]
            hash2 = unique_hashes[j]

            # Skip if vectors not available
            if hash1 not in file_vectors or hash2 not in file_vectors:
                continue

            # Compute similarity
            sim = engine.compute_similarity(
                file_vectors[hash1],
                file_vectors[hash2],
            )
            
            if sim > threshold:
                # Add all pairwise combinations
                for file1 in hash_to_files[hash1]:
                    for file2 in hash_to_files[hash2]:
                        near_duplicates.append({
                            "file1": os.path.basename(file1),
                            "file2": os.path.basename(file2),
                            "type": "near_duplicate",
                            "similarity": float(sim)
                        })
    
    # Combine results
    results = {
        "total_files": len(valid_files),
        "exact_duplicates": len(exact_duplicates),
        "near_duplicates": len(near_duplicates),
        "duplicates": exact_duplicates + near_duplicates
    }
    
    # Output results
    print(f"\nProcessed {results['total_files']} PDF files")
    print(f"Found {results['exact_duplicates']} exact duplicates")
    print(f"Found {results['near_duplicates']} near duplicates")
    
    if results['exact_duplicates'] > 0:
        print("\nExact Duplicates:")
        for dup in exact_duplicates:
            print(f"  - {dup['file1']} <-> {dup['file2']}")
    
    if results['near_duplicates'] > 0:
        print("\nNear Duplicates:")
        for dup in near_duplicates:
            print(f"  - {dup['file1']} <-> {dup['file2']} (similarity: {dup['similarity']:.3f})")
    
    # Save results to file if output path provided
    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "folder": folder_path,
                "results": results
            }, f, indent=2)
            
        print(f"\nResults saved to: {output_path}")
    
    return 0


def main() -> int:
    """
    Main entry point for the batch folder analysis CLI.
    
    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    parser = argparse.ArgumentParser(description="Analyze a folder of PDFs for duplicates.")
    parser.add_argument("folder", help="Folder containing PDFs")
    parser.add_argument("--threshold", type=float, default=0.9,
                       help="Similarity threshold (0-1)")
    parser.add_argument("--output", help="Output file for results (JSON)")
    
    if len(sys.argv) < 2:
        parser.print_help()
        return 1
    
    args = parser.parse_args()
    
    if not os.path.isdir(args.folder):
        logger.error(f"Folder not found: {args.folder}")
        return 1
    
    return batch_folder_check(args.folder, args.threshold, args.output)


if __name__ == "__main__":
    sys.exit(main())