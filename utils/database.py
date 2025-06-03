# utils/database.py
import logging
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, LargeBinary, ForeignKey, Text, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
import datetime
import pickle # For vector serialization if not handled elsewhere
from typing import Optional

from utils.config import settings # To get DATABASE_URL

logger = logging.getLogger(__name__)

SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL

try:
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base = declarative_base()
    logger.info("Database engine and session created successfully.")
except Exception as e:
    logger.error(f"Failed to create database engine or session: {e}", exc_info=True)
    # Define placeholders if DB setup fails, so other modules can import without immediate crash
    engine = None
    SessionLocal = None
    Base = object # So model classes can inherit from something


@contextmanager
def get_db() -> Session:
    """
    Provides a database session context.
    """
    if SessionLocal is None:
        logger.error("SessionLocal is not initialized. Database connection failed.")
        raise ConnectionError("Database session not available.")
        
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

# --- Model Definitions ---

class DocumentVector(Base if Base is not object else object): # type: ignore
    __tablename__ = "document_vectors"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(String, index=True, nullable=False) # This would be the main doc_id (UUID)
    vector_type = Column(String, index=True, nullable=False, default='tfidf') # e.g., 'tfidf'
    # Storing pickled numpy array. For pgvector, you'd use a Vector type.
    vector_data = Column(LargeBinary, nullable=False) 
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    __table_args__ = (Index('ix_doc_id_vec_type', 'document_id', 'vector_type', unique=True),)


class DocumentMetadata(Base if Base is not object else object): # type: ignore
    __tablename__ = "document_metadata"

    # Using the UUID doc_id directly as primary key
    doc_id = Column(String, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    upload_timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    last_processed_timestamp = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    status = Column(String, index=True, nullable=True) # e.g., "processing", "unique", "exact_duplicate", "content_duplicate", "error"
    content_hash = Column(String, index=True, unique=True, nullable=True) # SHA-256 hash
    minhash_signature = Column(Text, nullable=True) # Storing as hex string of the digest
    
    matched_doc_id = Column(String, nullable=True) # If duplicate, stores ID of the document it matched
    similarity_score = Column(Float, nullable=True) # e.g., TF-IDF similarity to matched_doc
    
    cluster_id = Column(String, index=True, nullable=True) # e.g., "cluster_1", "outlier"
    page_count = Column(Integer, nullable=True)
    
    # You could add more fields as needed, e.g., error_message

# Add other models if necessary, e.g., for LSH index bands if stored in DB, or exact hash log

def create_all_tables():
    """
    Creates all tables in the database.
    Should be called once during application startup or setup.
    """
    if engine is None:
        logger.error("Database engine is not initialized. Cannot create tables.")
        return
    try:
        logger.info("Creating database tables...")
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created (if they didn't exist).")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}", exc_info=True)

# --- CRUD Helper Functions for DocumentMetadata ---

def upsert_document_metadata(db: Session, doc_id: str, **kwargs) -> DocumentMetadata:
    """
    Creates a new DocumentMetadata entry or updates an existing one.
    Uses doc_id as the primary key for lookup.
    kwargs are used to set attributes on the DocumentMetadata object.
    """
    logger.debug(f"Upserting document metadata for doc_id: {doc_id} with data: {kwargs}")
    
    # Ensure last_processed_timestamp is updated
    kwargs['last_processed_timestamp'] = datetime.datetime.utcnow()
    
    # Check if 'filename' is provided for new entries, as it's non-nullable
    existing_entry = db.query(DocumentMetadata).filter(DocumentMetadata.doc_id == doc_id).first()
    
    if existing_entry:
        logger.debug(f"Updating existing metadata for {doc_id}")
        for key, value in kwargs.items():
            setattr(existing_entry, key, value)
        entry = existing_entry
    else:
        logger.debug(f"Creating new metadata for {doc_id}")
        if 'filename' not in kwargs:
            # This ideally should come from the initial processing step
            logger.warning(f"Filename not provided for new document metadata entry {doc_id}. Setting to 'Unknown'.")
            kwargs['filename'] = kwargs.get('filename', 'Unknown') # Default if still not there
        
        entry = DocumentMetadata(doc_id=doc_id, **kwargs)
        db.add(entry)
        
    try:
        db.commit()
        db.refresh(entry)
        logger.info(f"Successfully upserted document metadata for {doc_id}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error upserting document metadata for {doc_id}: {e}", exc_info=True)
        raise
    return entry

def get_document_metadata_by_id(db: Session, doc_id: str) -> Optional[DocumentMetadata]:
    """Retrieve document metadata by its primary key (doc_id)."""
    logger.debug(f"Fetching document metadata for doc_id: {doc_id}")
    try:
        return db.query(DocumentMetadata).filter(DocumentMetadata.doc_id == doc_id).first()
    except Exception as e:
        logger.error(f"Error fetching document metadata for {doc_id}: {e}", exc_info=True)
        return None

def get_document_by_hash(db: Session, content_hash: str) -> Optional[DocumentMetadata]:
    """Retrieve document metadata by its content_hash."""
    if not content_hash:
        logger.warning("Attempted to get document by None or empty hash.")
        return None
    logger.debug(f"Fetching document metadata by hash: {content_hash[:10]}...")
    try:
        return db.query(DocumentMetadata).filter(DocumentMetadata.content_hash == content_hash).first()
    except Exception as e:
        logger.error(f"Error fetching document by hash {content_hash[:10]}...: {e}", exc_info=True)
        return None

# (The vector CRUD functions are now mostly in similarity/tfidf.py but they will use get_db())