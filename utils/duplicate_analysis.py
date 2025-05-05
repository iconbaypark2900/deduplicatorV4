"""
Utility functions for analyzing document duplicates.
Provides methods for hashing, embedding, and comparing documents.
"""

import hashlib
import os
import numpy as np
from typing import List, Dict, Optional, Tuple, Union, Any
import logging
from datasketch import MinHash

# Import local modules
from similarity.tfidf import analyze_document_pages
from similarity.embedding import embed_text
from ingestion.pdf_reader import extract_text_from_pdf

# Set up logging
logger = logging.getLogger(__name__)


def compute_document_hash(pdf_path: str) -> Optional[str]:
    """
    Compute a hash for a document based on its text content.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        SHA256 hash of the document text, or None if text extraction fails
    """
    try:
        text = extract_text_from_pdf(pdf_path)
        if not text:
            logger.warning(f"No text extracted from {pdf_path}")
            return None
            
        # Hash the normalized text content
        return hashlib.sha256(text.strip().encode('utf-8')).hexdigest()
    except Exception as e:
        logger.error(f"Error computing document hash for {pdf_path}: {e}")
        return None


def compute_document_embedding(pdf_path: str) -> Optional[List[float]]:
    """
    Compute an embedding vector for a document based on its text content.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        Document embedding vector, or None if text extraction fails
    """
    try:
        text = extract_text_from_pdf(pdf_path)
        if not text:
            logger.warning(f"No text extracted from {pdf_path}")
            return None
            
        # Get embedding vector
        embedding = embed_text(text)
        return embedding
    except Exception as e:
        logger.error(f"Error computing document embedding for {pdf_path}: {e}")
        return None


def get_minhash(text: str, num_perm: int = 128) -> MinHash:
    """
    Create a MinHash object for a document text.
    Used for approximate similarity comparison.
    
    Args:
        text: Document text
        num_perm: Number of permutations for MinHash
        
    Returns:
        MinHash object
    """
    m = MinHash(num_perm=num_perm)
    
    # Create shingles (3-word sequences)
    words = text.split()
    for i in range(len(words) - 2):
        shingle = " ".join(words[i:i+3])
        m.update(shingle.encode('utf-8'))
        
    return m


def analyze_document_similarity(doc1_path: str, doc2_path: str, threshold: float = 0.85) -> Dict[str, Any]:
    """
    Analyze the similarity between two documents.
    
    Args:
        doc1_path: Path to the first PDF file
        doc2_path: Path to the second PDF file
        threshold: Similarity threshold for determining duplicates
        
    Returns:
        Dictionary with similarity results
        
    Raises:
        ValueError: If text extraction fails
    """
    # Extract text from both documents
    doc1_text = extract_text_from_pdf(doc1_path)
    doc2_text = extract_text_from_pdf(doc2_path)
    
    if not doc1_text or not doc2_text:
        raise ValueError("Could not extract text from one or both documents")
    
    # Compute document-level similarity using embeddings
    doc1_emb = embed_text(doc1_text)
    doc2_emb = embed_text(doc2_text)
    
    if not doc1_emb or not doc2_emb:
        raise ValueError("Could not compute embeddings for one or both documents")
    
    # Calculate cosine similarity
    from similarity.search import compute_similarity
    doc_similarity = compute_similarity(doc1_emb, doc2_emb)
    
    results = {
        "document_similarity": float(doc_similarity),
        "is_duplicate": doc_similarity >= threshold,
        "similar_pages": []
    }
    
    # If documents are similar, analyze at page level
    if doc_similarity >= threshold:
        from ingestion.pdf_reader import extract_pages_from_pdf
        
        # Get pages from both documents
        doc1_pages = extract_pages_from_pdf(doc1_path)
        doc2_pages = extract_pages_from_pdf(doc2_path)
        
        if doc1_pages and doc2_pages:
            # Create page data for page analysis
            page_data = []
            
            for i, text in enumerate(doc1_pages):
                page_data.append({
                    "page_num": i,
                    "text": text,
                    "document": "doc1"
                })
                
            for i, text in enumerate(doc2_pages):
                page_data.append({
                    "page_num": i,
                    "text": text,
                    "document": "doc2"
                })
                
            # Find similar pages across documents
            page_embeddings = [embed_text(page["text"]) for page in page_data]
            
            similar_pages = []
            for i in range(len(doc1_pages)):
                for j in range(len(doc2_pages)):
                    idx1 = i
                    idx2 = len(doc1_pages) + j
                    
                    if idx1 < len(page_embeddings) and idx2 < len(page_embeddings):
                        sim = compute_similarity(page_embeddings[idx1], page_embeddings[idx2])
                        
                        if sim >= threshold:
                            similar_pages.append({
                                "doc1_page": i,
                                "doc2_page": j,
                                "similarity": float(sim)
                            })
            
            results["similar_pages"] = similar_pages
            results["page_level_duplicate"] = len(similar_pages) > 0
    
    return results


def analyze_batch_duplicates(pdf_paths: List[str], threshold: float = 0.85) -> Dict[str, List[Dict[str, Any]]]:
    """
    Analyze a batch of documents for duplicates.
    
    Args:
        pdf_paths: List of paths to PDF files
        threshold: Similarity threshold for determining duplicates
        
    Returns:
        Dictionary with exact and near-duplicate results
    """
    results = {
        "exact_duplicates": [],
        "near_duplicates": []
    }
    
    # Step 1: Find exact duplicates by hash
    path_to_hash = {}
    hash_to_paths = {}
    
    for pdf_path in pdf_paths:
        doc_hash = compute_document_hash(pdf_path)
        if doc_hash:
            path_to_hash[pdf_path] = doc_hash
            
            if doc_hash not in hash_to_paths:
                hash_to_paths[doc_hash] = []
            hash_to_paths[doc_hash].append(pdf_path)
    
    # Collect exact duplicates
    for doc_hash, paths in hash_to_paths.items():
        if len(paths) > 1:
            for i in range(len(paths)):
                for j in range(i+1, len(paths)):
                    results["exact_duplicates"].append({
                        "file1": paths[i],
                        "file2": paths[j],
                        "type": "exact_duplicate"
                    })
    
    # Step 2: Find near-duplicates by embedding similarity
    path_to_embedding = {}
    
    for pdf_path in pdf_paths:
        # Skip if already found as exact duplicate
        if any(dup["file1"] == pdf_path or dup["file2"] == pdf_path 
               for dup in results["exact_duplicates"]):
            continue
            
        embedding = compute_document_embedding(pdf_path)
        if embedding:
            path_to_embedding[pdf_path] = embedding
    
    # Compare embeddings for near-duplicates
    from similarity.search import compute_similarity
    
    paths = list(path_to_embedding.keys())
    for i in range(len(paths)):
        for j in range(i+1, len(paths)):
            # Skip if already found as exact duplicate
            if any((dup["file1"] == paths[i] and dup["file2"] == paths[j]) or
                   (dup["file1"] == paths[j] and dup["file2"] == paths[i])
                   for dup in results["exact_duplicates"]):
                continue
                
            sim = compute_similarity(
                path_to_embedding[paths[i]],
                path_to_embedding[paths[j]]
            )
            
            if sim >= threshold:
                results["near_duplicates"].append({
                    "file1": paths[i],
                    "file2": paths[j],
                    "type": "near_duplicate",
                    "similarity": float(sim)
                })
    
    return results