# utils/database.py
import logging
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, LargeBinary, ForeignKey, Text, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from contextlib import contextmanager
import datetime
import pickle # For vector serialization if not handled elsewhere
from typing import Optional, Generator

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
def get_db() -> Generator[Session, None, None]:
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

class DocumentVector(Base): # type: ignore
    __tablename__ = "document_vectors"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(String, ForeignKey('document_metadata.doc_id'), index=True, nullable=False)
    vector_type = Column(String, index=True, nullable=False, default='tfidf')
    vector_data = Column(LargeBinary, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    __table_args__ = (Index('ix_doc_id_vec_type_doc_vector', 'document_id', 'vector_type', unique=True),)

    document = relationship("DocumentMetadata", back_populates="vectors")


class DocumentMetadata(Base): # type: ignore
    __tablename__ = "document_metadata"

    doc_id = Column(String, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    upload_timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    last_processed_timestamp = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    status = Column(String, index=True, nullable=True)
    content_hash = Column(String, index=True, unique=True, nullable=True)
    minhash_signature = Column(LargeBinary, nullable=True)
    matched_doc_id = Column(String, ForeignKey('document_metadata.doc_id'), nullable=True)
    similarity_score = Column(Float, nullable=True)
    cluster_id = Column(String, index=True, nullable=True)
    page_count = Column(Integer, nullable=True)

    # Relationships
    pages = relationship("Page", back_populates="document", cascade="all, delete-orphan")
    vectors = relationship("DocumentVector", back_populates="document", cascade="all, delete-orphan")
    sections = relationship("DocumentSection", back_populates="document", cascade="all, delete-orphan")
    medical_entities = relationship("MedicalEntity", back_populates="document", cascade="all, delete-orphan")
    review_history_entries = relationship("ReviewHistory", back_populates="document", cascade="all, delete-orphan")

    # For duplicate relationships
    source_for_duplicates = relationship(
        "DuplicateRelationship",
        foreign_keys="[DuplicateRelationship.source_document_id]",
        back_populates="source_document",
        cascade="all, delete-orphan"
    )
    duplicate_of_documents = relationship(
        "DuplicateRelationship",
        foreign_keys="[DuplicateRelationship.duplicate_document_id]",
        back_populates="duplicate_document",
        cascade="all, delete-orphan"
    )


class Page(Base): # type: ignore
    __tablename__ = "pages"
    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(String, ForeignKey("document_metadata.doc_id"), nullable=False)
    page_number = Column(Integer, nullable=False)
    page_hash = Column(String, nullable=False, index=True)
    text_snippet = Column(Text, nullable=True)
    page_image_path = Column(String, nullable=True)
    medical_confidence = Column(Float, nullable=True)
    duplicate_confidence = Column(Float, nullable=True)
    status = Column(String(50), default="pending")

    document = relationship("DocumentMetadata", back_populates="pages")
    vector = relationship("PageVector", back_populates="page", uselist=False, cascade="all, delete-orphan")
    medical_entities = relationship("MedicalEntity", back_populates="page", cascade="all, delete-orphan")
    review_decisions = relationship("PageReviewDecision", back_populates="page", cascade="all, delete-orphan")

    source_for_page_duplicates = relationship(
        "PageDuplicate",
        foreign_keys="[PageDuplicate.source_page_id]",
        back_populates="source_page",
        cascade="all, delete-orphan"
    )
    duplicate_of_pages = relationship(
        "PageDuplicate",
        foreign_keys="[PageDuplicate.duplicate_page_id]",
        back_populates="duplicate_page",
        cascade="all, delete-orphan"
    )
    __table_args__ = (Index('ix_doc_id_page_num', 'document_id', 'page_number', unique=True),)


class DuplicateRelationship(Base): # type: ignore
    __tablename__ = "duplicate_relationships"
    id = Column(Integer, primary_key=True, autoincrement=True)
    source_document_id = Column(String, ForeignKey("document_metadata.doc_id"), nullable=False)
    duplicate_document_id = Column(String, ForeignKey("document_metadata.doc_id"), nullable=False)
    similarity = Column(Float, nullable=False)
    detection_method = Column(String(50), nullable=True)
    detection_timestamp = Column(DateTime, default=datetime.datetime.utcnow)

    source_document = relationship("DocumentMetadata", foreign_keys=[source_document_id], back_populates="source_for_duplicates")
    duplicate_document = relationship("DocumentMetadata", foreign_keys=[duplicate_document_id], back_populates="duplicate_of_documents")
    __table_args__ = (Index('ix_source_dup_doc', 'source_document_id', 'duplicate_document_id', unique=True),)


class PageDuplicate(Base): # type: ignore
    __tablename__ = "page_duplicates"
    id = Column(Integer, primary_key=True, autoincrement=True)
    source_page_id = Column(Integer, ForeignKey("pages.id"), nullable=False)
    duplicate_page_id = Column(Integer, ForeignKey("pages.id"), nullable=False)
    similarity = Column(Float, nullable=False)

    source_page = relationship("Page", foreign_keys=[source_page_id], back_populates="source_for_page_duplicates")
    duplicate_page = relationship("Page", foreign_keys=[duplicate_page_id], back_populates="duplicate_of_pages")
    __table_args__ = (Index('ix_source_dup_page', 'source_page_id', 'duplicate_page_id', unique=True),)


class PageVector(Base): # type: ignore
    __tablename__ = "page_vectors"
    page_id = Column(Integer, ForeignKey("pages.id"), primary_key=True)
    vector_type = Column(String(50), nullable=False, default='tfidf')
    vector_data = Column(LargeBinary, nullable=False)

    page = relationship("Page", back_populates="vector")


class User(Base): # type: ignore
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(255), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=True)
    role = Column(String(50), default="reviewer")

    review_history_entries = relationship("ReviewHistory", back_populates="user", cascade="all, delete-orphan")
    page_review_decisions = relationship("PageReviewDecision", back_populates="user", cascade="all, delete-orphan")


class ReviewHistory(Base): # type: ignore
    __tablename__ = "review_history"
    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(String, ForeignKey("document_metadata.doc_id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    decision = Column(String(50), nullable=False)
    notes = Column(Text, nullable=True)
    review_timestamp = Column(DateTime, default=datetime.datetime.utcnow)

    document = relationship("DocumentMetadata", back_populates="review_history_entries")
    user = relationship("User", back_populates="review_history_entries")


    
    status = Column(String, index=True, nullable=True) # e.g., "processing", "unique", "exact_duplicate", "content_duplicate", "error"
    content_hash = Column(String, index=True, unique=True, nullable=True) # SHA-256 hash
    minhash_signature = Column(Text, nullable=True) # Storing as hex string of the digest
    
    matched_doc_id = Column(String, nullable=True) # If duplicate, stores ID of the document it matched
    similarity_score = Column(Float, nullable=True) # e.g., TF-IDF similarity to matched_doc
    
    cluster_id = Column(String, index=True, nullable=True) # e.g., "cluster_1", "outlier"
    page_count = Column(Integer, nullable=True)
    
    # You could add more fields as needed, e.g., error_message

class PageReviewDecision(Base): # type: ignore
    __tablename__ = "page_review_decisions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    page_id = Column(Integer, ForeignKey("pages.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    decision = Column(String(50), nullable=False)
    notes = Column(Text, nullable=True)
    review_timestamp = Column(DateTime, default=datetime.datetime.utcnow)

    page = relationship("Page", back_populates="review_decisions")
    user = relationship("User", back_populates="page_review_decisions")


class DocumentSection(Base): # type: ignore
    __tablename__ = "document_sections"
    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(String, ForeignKey("document_metadata.doc_id"), nullable=False)
    section_title = Column(String, nullable=False)
    section_text = Column(Text, nullable=True)

    document = relationship("DocumentMetadata", back_populates="sections")


class MedicalEntity(Base): # type: ignore
    __tablename__ = "medical_entities"
    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(String, ForeignKey("document_metadata.doc_id"), nullable=False)
    page_id = Column(Integer, ForeignKey("pages.id"), nullable=True)
    entity_type = Column(String, nullable=False)
    entity_value = Column(String, nullable=False)
    confidence = Column(Float, nullable=True)

    document = relationship("DocumentMetadata", back_populates="medical_entities")
    page = relationship("Page", back_populates="medical_entities")

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

# --- CRUD Helper Functions for Page ---

def create_page(db: Session, document_id: str, page_number: int, page_hash: str, 
                text_snippet: Optional[str] = None, 
                page_image_path: Optional[str] = None,
                medical_confidence: Optional[float] = None,
                duplicate_confidence: Optional[float] = None,
                status: str = "pending") -> Page:
    """Creates a new Page entry."""
    logger.debug(f"Creating page for document_id: {document_id}, page_number: {page_number}")
    page = Page(
        document_id=document_id,
        page_number=page_number,
        page_hash=page_hash,
        text_snippet=text_snippet,
        page_image_path=page_image_path,
        medical_confidence=medical_confidence,
        duplicate_confidence=duplicate_confidence,
        status=status
    )
    db.add(page)
    try:
        db.commit()
        db.refresh(page)
        logger.info(f"Successfully created page {page.id} for document {document_id}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating page for document {document_id}, page {page_number}: {e}", exc_info=True)
        raise
    return page

def get_page(db: Session, page_id: int) -> Optional[Page]:
    """Retrieve a page by its ID."""
    logger.debug(f"Fetching page with id: {page_id}")
    try:
        return db.query(Page).filter(Page.id == page_id).first()
    except Exception as e:
        logger.error(f"Error fetching page {page_id}: {e}", exc_info=True)
        return None

def get_page_by_doc_and_page_num(db: Session, document_id: str, page_number: int) -> Optional[Page]:
    """Retrieve a page by its document ID and page number."""
    logger.debug(f"Fetching page for document_id: {document_id}, page_number: {page_number}")
    try:
        return db.query(Page).filter(Page.document_id == document_id, Page.page_number == page_number).first()
    except Exception as e:
        logger.error(f"Error fetching page for document {document_id}, page {page_number}: {e}", exc_info=True)
        return None

def get_pages_by_document_id(db: Session, document_id: str) -> list[Page]:
    """Retrieve all pages for a given document_id."""
    logger.debug(f"Fetching all pages for document_id: {document_id}")
    try:
        return db.query(Page).filter(Page.document_id == document_id).order_by(Page.page_number).all()
    except Exception as e:
        logger.error(f"Error fetching pages for document {document_id}: {e}", exc_info=True)
        return []

def update_page(db: Session, page_id: int, **kwargs) -> Optional[Page]:
    """Updates a Page entry."""
    logger.debug(f"Updating page with id: {page_id} with data: {kwargs}")
    page = db.query(Page).filter(Page.id == page_id).first()
    if page:
        for key, value in kwargs.items():
            setattr(page, key, value)
        try:
            db.commit()
            db.refresh(page)
            logger.info(f"Successfully updated page {page_id}")
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating page {page_id}: {e}", exc_info=True)
            raise
        return page
    logger.warning(f"Page with id {page_id} not found for update.")
    return None


# --- CRUD Helper Functions for User ---

def create_user(db: Session, username: str, email: str, password_hash: Optional[str] = None, role: str = "reviewer") -> User:
    """Creates a new User entry."""
    logger.debug(f"Creating user: {username}")
    user = User(username=username, email=email, password_hash=password_hash, role=role)
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
        logger.info(f"Successfully created user {username} (ID: {user.id})")
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating user {username}: {e}", exc_info=True)
        raise
    return user

def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    """Retrieve a user by their ID."""
    logger.debug(f"Fetching user with id: {user_id}")
    try:
        return db.query(User).filter(User.id == user_id).first()
    except Exception as e:
        logger.error(f"Error fetching user {user_id}: {e}", exc_info=True)
        return None

def get_user_by_username(db: Session, username: str) -> Optional[User]:
    """Retrieve a user by their username."""
    logger.debug(f"Fetching user by username: {username}")
    try:
        return db.query(User).filter(User.username == username).first()
    except Exception as e:
        logger.error(f"Error fetching user by username {username}: {e}", exc_info=True)
        return None

# --- CRUD Helper Functions for ReviewHistory ---

def create_review_history_entry(db: Session, document_id: str, decision: str, 
                                user_id: Optional[int] = None, 
                                notes: Optional[str] = None) -> ReviewHistory:
    """Creates a new ReviewHistory entry."""
    logger.debug(f"Creating review history for document_id: {document_id}, decision: {decision}")
    entry = ReviewHistory(document_id=document_id, user_id=user_id, decision=decision, notes=notes)
    db.add(entry)
    try:
        db.commit()
        db.refresh(entry)
        logger.info(f"Successfully created review history entry {entry.id} for document {document_id}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating review history for document {document_id}: {e}", exc_info=True)
        raise
    return entry

def get_review_history_for_document(db: Session, document_id: str) -> list[ReviewHistory]:
    """Retrieve all review history entries for a given document_id."""
    logger.debug(f"Fetching review history for document_id: {document_id}")
    try:
        return db.query(ReviewHistory).filter(ReviewHistory.document_id == document_id).order_by(ReviewHistory.review_timestamp.desc()).all()
    except Exception as e:
        logger.error(f"Error fetching review history for document {document_id}: {e}", exc_info=True)
        return []

# (The vector CRUD functions are now mostly in similarity/tfidf.py but they will use get_db())