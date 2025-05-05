"""
TF-IDF based document similarity.
Implements term frequency-inverse document frequency for text comparison.
"""

import re
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import json
import os
import pickle
from typing import Dict, List, Optional, Tuple, Union
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# File paths for TF-IDF persistence
VECTORIZER_FILE = "storage/metadata/tfidf_vectorizer.pkl"
CORPUS_FILE = "storage/metadata/tfidf_corpus.json"
CORPUS_TEXTS_FILE = "storage/metadata/tfidf_texts.json"

# Ensure paths exist
os.makedirs("storage/metadata", exist_ok=True)

# Global vectorizer instance
VECTORIZER = None


def preprocess_text(text: str) -> str:
    """
    Preprocess text for TF-IDF vectorization.
    Lowercase, strip, and remove punctuation.
    
    Args:
        text: Text to preprocess
        
    Returns:
        Preprocessed text
    """
    text = text.lower().strip()
    # Remove punctuation except hyphens which are important in medical terms
    text = re.sub(r'[^\w\s-]', '', text)
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)
    return text


def _load_vectorizer() -> TfidfVectorizer:
    """
    Load the fitted TF-IDF vectorizer from file or initialize it.
    Uses caching to avoid reloading the model for each embedding.
    
    Returns:
        TF-IDF vectorizer
    """
    global VECTORIZER
    if VECTORIZER is None:
        if os.path.exists(VECTORIZER_FILE):
            with open(VECTORIZER_FILE, "rb") as f:
                try:
                    VECTORIZER = pickle.load(f)
                    logger.info("Loaded existing TF-IDF vectorizer")
                except Exception as e:
                    logger.error(f"Error loading vectorizer: {e}")
                    VECTORIZER = TfidfVectorizer(ngram_range=(1, 2), stop_words='english')
        else:
            logger.info("Creating new TF-IDF vectorizer")
            VECTORIZER = TfidfVectorizer(ngram_range=(1, 2), stop_words='english')
    return VECTORIZER


def _save_vectorizer(vectorizer: TfidfVectorizer) -> None:
    """
    Save the fitted TF-IDF vectorizer to file.
    
    Args:
        vectorizer: TF-IDF vectorizer to save
    """
    try:
        with open(VECTORIZER_FILE, "wb") as f:
            pickle.dump(vectorizer, f)
            logger.info("Saved TF-IDF vectorizer")
    except Exception as e:
        logger.error(f"Error saving vectorizer: {e}")


def _load_corpus() -> Dict[str, List[float]]:
    """
    Load the TF-IDF corpus from file.
    
    Returns:
        Dictionary mapping document names to TF-IDF vectors
    """
    if os.path.exists(CORPUS_FILE):
        try:
            with open(CORPUS_FILE, "r") as f:
                corpus = json.load(f)
                logger.info(f"Loaded corpus with {len(corpus)} documents")
                return corpus
        except Exception as e:
            logger.error(f"Error loading corpus: {e}")
    logger.info("No corpus found, starting with empty corpus")
    return {}


def _load_texts() -> Dict[str, str]:
    """
    Load the original texts from file.
    
    Returns:
        Dictionary mapping document names to original texts
    """
    if os.path.exists(CORPUS_TEXTS_FILE):
        try:
            with open(CORPUS_TEXTS_FILE, "r") as f:
                texts = json.load(f)
                logger.info(f"Loaded texts for {len(texts)} documents")
                return texts
        except Exception as e:
            logger.error(f"Error loading texts: {e}")
    logger.info("No texts found, starting with empty texts")
    return {}


def _save_corpus(corpus: Dict[str, List[float]]) -> None:
    """
    Save the TF-IDF corpus to file.
    
    Args:
        corpus: Dictionary mapping document names to TF-IDF vectors
    """
    try:
        with open(CORPUS_FILE, "w") as f:
            json.dump(corpus, f)
            logger.info(f"Saved corpus with {len(corpus)} documents")
    except Exception as e:
        logger.error(f"Error saving corpus: {e}")


def _save_texts(texts: Dict[str, str]) -> None:
    """
    Save the original texts to file.
    
    Args:
        texts: Dictionary mapping document names to original texts
    """
    try:
        with open(CORPUS_TEXTS_FILE, "w") as f:
            json.dump(texts, f)
            logger.info(f"Saved texts for {len(texts)} documents")
    except Exception as e:
        logger.error(f"Error saving texts: {e}")


def update_tfidf_corpus(text: str, doc_name: str) -> None:
    """
    Update the TF-IDF corpus with a new document.
    
    Args:
        text: Document text
        doc_name: Document identifier
    """
    # Load existing data
    corpus = _load_corpus()
    texts = _load_texts()
    vectorizer = _load_vectorizer()
    
    # Add new document
    texts[doc_name] = text
    
    # Get all texts in order
    all_texts = list(texts.values())
    all_docs = list(texts.keys())
    
    # Preprocess texts
    processed_texts = [preprocess_text(t) for t in all_texts]
    
    # Fit vectorizer and transform all documents
    try:
        logger.info(f"Fitting vectorizer on {len(processed_texts)} documents")
        vectors = vectorizer.fit_transform(processed_texts).toarray()
        
        # Update corpus with new vectors
        corpus = {doc: vec.tolist() for doc, vec in zip(all_docs, vectors)}
        
        # Save updated data
        _save_corpus(corpus)
        _save_texts(texts)
        _save_vectorizer(vectorizer)
        logger.info(f"Added {doc_name} to corpus (now {len(corpus)} documents)")
    except Exception as e:
        logger.error(f"Error updating corpus: {e}")
        raise
    
def tfidf_vectorize(text: str) -> np.ndarray:
    """
    Convert text into a TF-IDF vector using the pre-fitted vectorizer.
    
    Args:
        text: Text to vectorize
        
    Returns:
        TF-IDF vector
        
    Raises:
        ValueError: If the vectorizer is not fitted
    """
    vectorizer = _load_vectorizer()
    if not hasattr(vectorizer, 'vocabulary_') or not vectorizer.vocabulary_:
        raise ValueError("The TF-IDF vectorizer is not fitted")
    
    text = preprocess_text(text)
    return vectorizer.transform([text]).toarray()[0]


def tfidf_search(query_vector: np.ndarray, threshold: float = 0.85) -> Optional[Dict]:
    """
    Compare the query vector against the stored corpus of TF-IDF vectors.
    
    Args:
        query_vector: Query TF-IDF vector
        threshold: Similarity threshold for determining matches
        
    Returns:
        Match information if similarity exceeds threshold, else None
    """
    corpus = _load_corpus()
    if not corpus:
        logger.info("Empty corpus, no matches possible")
        return None
    
    best_match = None
    best_sim = 0.0
    
    for doc_name, vec in corpus.items():
        vec = np.array(vec)
        # Calculate cosine similarity
        sim = np.dot(query_vector, vec) / (np.linalg.norm(query_vector) * np.linalg.norm(vec) + 1e-8)
        if sim > best_sim:
            best_sim = sim
            best_match = doc_name
    
    if best_sim >= threshold:
        logger.info(f"Found match: {best_match} with similarity {best_sim:.4f}")
        return {
            "matched_doc": best_match,
            "similarity": round(best_sim, 4)
        }
    
    logger.info(f"No match found (best: {best_match} at {best_sim:.4f}, threshold: {threshold})")
    return None


def analyze_document_pages(pages: List[Union[str, Dict]], threshold: float = 0.85) -> List[Dict]:
    """
    Analyze a document's pages for duplicate content.
    
    Args:
        pages: List of page texts or dictionaries with text_snippet field
        threshold: Similarity threshold for flagging duplicates
        
    Returns:
        List of dictionaries with duplicate page information
        
    Raises:
        ValueError: If pages is empty or contains invalid data
    """
    logger.debug(f"Starting page analysis with {len(pages)} pages and threshold {threshold}")
    
    if not pages:
        logger.warning("No pages provided for analysis")
        return []
    
    # Extract text content from pages if they are dictionaries
    page_texts = []
    for page in pages:
        if isinstance(page, dict):
            text = page.get('text_snippet', '')
            if not text and 'text' in page:
                text = page.get('text', '')
            logger.debug(f"Extracted text from dictionary: {text[:100]}...")
            page_texts.append(text)
        else:
            page_texts.append(page)
    
    # Preprocess all pages
    logger.debug("Preprocessing pages")
    processed_pages = [preprocess_text(page) for page in page_texts]
    logger.debug(f"Preprocessed pages lengths: {[len(p) for p in processed_pages]}")
    
    # Create a new vectorizer for this document only
    logger.debug("Creating new TF-IDF vectorizer for page analysis")
    vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words='english')
    
    try:
        # Fit and transform all pages
        logger.debug("Fitting and transforming pages")
        vectors = vectorizer.fit_transform(processed_pages).toarray()
        logger.debug(f"Vector shape: {vectors.shape}")
        
        # Find similar page pairs
        similar_pairs = []
        n_pages = len(pages)
        logger.debug(f"Comparing {n_pages} pages")
        
        for i in range(n_pages):
            for j in range(i + 1, n_pages):
                # Calculate cosine similarity
                sim = np.dot(vectors[i], vectors[j]) / (np.linalg.norm(vectors[i]) * np.linalg.norm(vectors[j]) + 1e-8)
                
                if sim >= threshold:
                    logger.debug(f"Found similar pages {i} and {j} with similarity {sim:.4f}")
                    similar_pairs.append({
                        "page1_idx": i,
                        "page2_idx": j,
                        "similarity": float(sim)
                    })
        
        logger.debug(f"Analysis complete. Found {len(similar_pairs)} similar pairs")
        return similar_pairs
        
    except Exception as e:
        logger.error(f"Error during page analysis: {str(e)}")
        raise