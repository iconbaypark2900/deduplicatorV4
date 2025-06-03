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
from typing import Dict, List, Optional, Tuple, Union, Any
import logging

# Attempt to import database utilities and model
try:
    from utils.database import get_db, DocumentVector # Assuming DocumentVector is your SQLAlchemy model
    from sqlalchemy.orm import Session # For type hinting
except ImportError:
    logger.warning(
        "Could not import database utilities (get_db, DocumentVector) or Session. "
        "Database operations will not work. Ensure utils.database is set up."
    )
    # Define placeholders if imports fail, to allow basic script parsing
    get_db = None
    DocumentVector = None
    Session = None 

# Set up logging
# logging.basicConfig(level=logging.INFO) # Moved to be configured by the application
logger = logging.getLogger(__name__)

# File paths for TF-IDF persistence
VECTORIZER_FILE = "storage/metadata/tfidf_vectorizer.pkl"
CORPUS_FILE = "storage/metadata/tfidf_corpus.json"
CORPUS_TEXTS_FILE = "storage/metadata/tfidf_texts.json"

# Ensure paths exist
os.makedirs("storage/metadata", exist_ok=True)

# Global vectorizer instance
VECTORIZER = None

# --- Database Helper Functions --- 
def _vector_to_binary(vector: np.ndarray) -> bytes:
    """Serialize numpy array to bytes."""
    return pickle.dumps(vector) # Using pickle for numpy arrays is common

def _binary_to_vector(data: bytes) -> np.ndarray:
    """Deserialize bytes to numpy array."""
    return pickle.loads(data)

def insert_document_vector(db: Session, doc_id: str, vector: np.ndarray, vector_type: str = 'tfidf'):
    """Insert or update a document vector in the database."""
    if not db or not DocumentVector:
        logger.error("Database session or DocumentVector model not available for insert_document_vector.")
        return
    try:
        existing_vector = db.query(DocumentVector).filter_by(document_id=doc_id, vector_type=vector_type).first()
        binary_vector = _vector_to_binary(vector)
        
        if existing_vector:
            existing_vector.vector_data = binary_vector
            logger.info(f"Updated vector for {doc_id} ({vector_type}) in DB.")
        else:
            db_vector = DocumentVector(
                document_id=doc_id,
                vector_type=vector_type,
                vector_data=binary_vector
            )
            db.add(db_vector)
            logger.info(f"Inserted new vector for {doc_id} ({vector_type}) into DB.")
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Error in insert_document_vector for {doc_id}: {e}", exc_info=True)
        raise

def get_document_vector(db: Session, doc_id: str, vector_type: str = 'tfidf') -> Optional[np.ndarray]:
    """Retrieve a specific document vector from the database."""
    if not db or not DocumentVector:
        logger.error("Database session or DocumentVector model not available for get_document_vector.")
        return None
    try:
        db_vector = db.query(DocumentVector).filter_by(document_id=doc_id, vector_type=vector_type).first()
        if db_vector:
            return _binary_to_vector(db_vector.vector_data)
        return None
    except Exception as e:
        logger.error(f"Error in get_document_vector for {doc_id}: {e}", exc_info=True)
        return None

def get_all_document_vectors(db: Session, vector_type: str = 'tfidf') -> List[Tuple[str, np.ndarray]]:
    """Retrieve all document vectors of a specific type from the database."""
    if not db or not DocumentVector:
        logger.error("Database session or DocumentVector model not available for get_all_document_vectors.")
        return []
    try:
        vectors_data = db.query(DocumentVector.document_id, DocumentVector.vector_data).filter_by(vector_type=vector_type).all()
        return [(doc_id, _binary_to_vector(vec_data)) for doc_id, vec_data in vectors_data]
    except Exception as e:
        logger.error(f"Error in get_all_document_vectors for {vector_type}: {e}", exc_info=True)
        return []

# --- End Database Helper Functions ---


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


def _load_vectorizer() -> Optional[TfidfVectorizer]:
    """
    Load the fitted TF-IDF vectorizer from file.
    Returns the vectorizer if found and loaded, else None or an unfitted instance.
    """
    global VECTORIZER
    if VECTORIZER is not None: # Return cached instance if available
        return VECTORIZER

    if os.path.exists(VECTORIZER_FILE):
        try:
            with open(VECTORIZER_FILE, "rb") as f:
                VECTORIZER = pickle.load(f)
                logger.info("Loaded existing TF-IDF vectorizer from file.")
                if hasattr(VECTORIZER, 'vocabulary_') and VECTORIZER.vocabulary_:
                    return VECTORIZER
                else:
                    logger.warning("Loaded vectorizer from file is not fitted.")
                    # Return the unfitted instance; calling function must check
                    return VECTORIZER 
        except Exception as e:
            logger.error(f"Error loading vectorizer from {VECTORIZER_FILE}: {e}. Returning new unfitted instance.")
            # Fallback to a new, unfitted vectorizer instance
            VECTORIZER = TfidfVectorizer(ngram_range=(1, 2), stop_words='english')
            return VECTORIZER
    else:
        logger.warning(f"Vectorizer file {VECTORIZER_FILE} not found. Returning new unfitted instance.")
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


# def _load_corpus() -> Dict[str, List[float]]:
#     """
#     Load the TF-IDF corpus from file.
#     
#     Returns:
#         Dictionary mapping document names to TF-IDF vectors
#     """
#     if os.path.exists(CORPUS_FILE):
#         try:
#             with open(CORPUS_FILE, "r") as f:
#                 corpus = json.load(f)
#                 logger.info(f"Loaded corpus with {len(corpus)} documents")
#                 return corpus
#         except Exception as e:
#             logger.error(f"Error loading corpus: {e}")
#     logger.info("No corpus found, starting with empty corpus")
#     return {}
# 
# 
# def _load_texts() -> Dict[str, str]:
#     """
#     Load the original texts from file.
#     
#     Returns:
#         Dictionary mapping document names to original texts
#     """
#     if os.path.exists(CORPUS_TEXTS_FILE):
#         try:
#             with open(CORPUS_TEXTS_FILE, "r") as f:
#                 texts = json.load(f)
#                 logger.info(f"Loaded texts for {len(texts)} documents")
#                 return texts
#         except Exception as e:
#             logger.error(f"Error loading texts: {e}")
#     logger.info("No texts found, starting with empty texts")
#     return {}
# 
# 
# def _save_corpus(corpus: Dict[str, List[float]]) -> None:
#     """
#     Save the TF-IDF corpus to file.
#     
#     Args:
#         corpus: Dictionary mapping document names to TF-IDF vectors
#     """
#     try:
#         with open(CORPUS_FILE, "w") as f:
#             json.dump(corpus, f)
#             logger.info(f"Saved corpus with {len(corpus)} documents")
#     except Exception as e:
#         logger.error(f"Error saving corpus: {e}")
# 
# 
# def _save_texts(texts: Dict[str, str]) -> None:
#     """
#     Save the original texts to file.
#     
#     Args:
#         texts: Dictionary mapping document names to original texts
#     """
#     try:
#         with open(CORPUS_TEXTS_FILE, "w") as f:
#             json.dump(texts, f)
#             logger.info(f"Saved texts for {len(texts)} documents")
#     except Exception as e:
#         logger.error(f"Error saving texts: {e}")


def update_tfidf_corpus(text: str, doc_name: str) -> None:
    """
    Updates the system with a new document by generating its TF-IDF vector 
    using a pre-fitted vectorizer and storing it in the database.
    
    Args:
        text: Document text
        doc_name: Document identifier
    """
    if get_db is None or insert_document_vector is None:
        logger.error("Database utilities are not available. Cannot update TF-IDF corpus in DB.")
        return

    vectorizer = _load_vectorizer()
    if vectorizer is None or not hasattr(vectorizer, 'vocabulary_') or not vectorizer.vocabulary_:
        logger.error(
            f"TF-IDF vectorizer is not fitted. Cannot process document {doc_name}. "
            "Please fit and save the vectorizer first (e.g., using fit_vectorizer_and_save())."
        )
        return

    processed_text = preprocess_text(text)
    if not processed_text.strip():
        logger.warning(f"Document {doc_name} has no content after preprocessing. Skipping vectorization.")
        # Optionally, store a zero vector or handle as an error/specific status in DB
        # For now, we just skip insertion.
        return

    try:
        new_vector = vectorizer.transform([processed_text]).toarray()[0]
        
        with get_db() as db: # Assuming get_db is a context manager yielding a session
            insert_document_vector(db, doc_name, new_vector, 'tfidf')
        logger.info(f"Successfully processed and stored TF-IDF vector for {doc_name}.")
    except Exception as e:
        logger.error(f"Error vectorizing or storing document {doc_name}: {e}", exc_info=True)
        # Not re-raising here to allow batch processing to potentially continue
    
def fit_vectorizer_and_save(texts: List[str], vectorizer_path: str = VECTORIZER_FILE) -> TfidfVectorizer:
    """
    Fits a new TfidfVectorizer on the provided texts and saves it.
    This should be called as part of a setup or retraining process.

    Args:
        texts: A list of raw text documents to fit the vectorizer on.
        vectorizer_path: Path to save the fitted vectorizer.

    Returns:
        The fitted TfidfVectorizer instance.
    """
    global VECTORIZER
    logger.info(f"Starting to fit a new TF-IDF vectorizer on {len(texts)} documents.")
    new_vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words='english', max_df=0.95, min_df=2)
    
    processed_texts = [preprocess_text(text) for text in texts]
    new_vectorizer.fit(processed_texts)
    logger.info("TF-IDF vectorizer fitting complete.")
    
    _save_vectorizer(new_vectorizer) # Save it to the default path or specified one
    VECTORIZER = new_vectorizer # Update global cache
    return new_vectorizer

    
def tfidf_vectorize(text: str) -> Optional[np.ndarray]:
    """
    Convert text into a TF-IDF vector using the pre-fitted vectorizer.
    
    Args:
        text: Text to vectorize
        
    Returns:
        TF-IDF vector, or None if vectorizer is not fitted or text is empty.
        
    Raises:
        ValueError: If the vectorizer is not fitted (should be caught by check)
    """
    vectorizer = _load_vectorizer()
    if vectorizer is None or not hasattr(vectorizer, 'vocabulary_') or not vectorizer.vocabulary_:
        logger.error("The TF-IDF vectorizer is not fitted. Cannot vectorize text.")
        # raise ValueError("The TF-IDF vectorizer is not fitted") # Or return None
        return None 
    
    processed_text = preprocess_text(text)
    if not processed_text.strip():
        logger.warning("Attempted to vectorize empty or all-whitespace text.")
        # Depending on vectorizer settings, this might produce a zero vector or error.
        # For consistency, let's return a zero vector of the correct dimension or handle as error.
        # For now, returning None as TFIDF for empty string is problematic.
        return None
    return vectorizer.transform([processed_text]).toarray()[0]


def tfidf_search(query_vector: np.ndarray, threshold: float = 0.85) -> Optional[Dict]:
    """
    Compare the query vector against TF-IDF vectors stored in the database.
    
    Args:
        query_vector: Query TF-IDF vector
        threshold: Similarity threshold for determining matches
        
    Returns:
        Match information if similarity exceeds threshold, else None
    """
    if get_db is None or get_all_document_vectors is None:
        logger.error("Database utilities are not available. Cannot perform TF-IDF search.")
        return None

    if query_vector is None or query_vector.size == 0:
        logger.warning("Received an empty or None query vector for TF-IDF search.")
        return None

    best_match_doc_id = None
    best_sim = -1.0 # Initialize to a value lower than any possible cosine similarity
    
    try:
        with get_db() as db:
            all_doc_vectors = get_all_document_vectors(db, 'tfidf')
        
        if not all_doc_vectors:
            logger.info("No TF-IDF vectors found in the database to search against.")
            return None
        
        query_norm = np.linalg.norm(query_vector)
        if query_norm == 0:
            logger.warning("Query vector has zero norm. Cannot compute similarity.")
            return None
            
        for doc_id, doc_vec_array in all_doc_vectors:
            if doc_vec_array is None or doc_vec_array.size == 0:
                logger.warning(f"Skipping document {doc_id} due to empty or None vector in DB.")
                continue

            doc_norm = np.linalg.norm(doc_vec_array)
            if doc_norm == 0:
                logger.warning(f"Skipping document {doc_id} due to zero norm vector in DB.")
                continue
            
            # Ensure vectors are 1D for dot product if they are not already (e.g. (1, N) shape)
            q_vec = query_vector.flatten()
            d_vec = doc_vec_array.flatten()

            if q_vec.shape != d_vec.shape:
                logger.warning(f"Shape mismatch between query vector ({q_vec.shape}) and DB vector for {doc_id} ({d_vec.shape}). Skipping.")
                continue

            sim = np.dot(q_vec, d_vec) / (query_norm * doc_norm)
            
            if sim > best_sim:
                best_sim = sim
                best_match_doc_id = doc_id
        
        if best_match_doc_id is not None and best_sim >= threshold:
            logger.info(f"TF-IDF search found match: {best_match_doc_id} with similarity {best_sim:.4f}")
            return {
                "matched_doc": best_match_doc_id,
                "similarity": round(float(best_sim), 4) # Ensure float for JSON serialization
            }
        
        logger.info(f"TF-IDF search no match found (best: {best_match_doc_id} at {best_sim:.4f}, threshold: {threshold})")
        return None

    except Exception as e:
        logger.error(f"Error during TF-IDF search: {e}", exc_info=True)
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