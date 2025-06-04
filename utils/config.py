"""
Configuration settings for the PDF deduplication system.
Uses Pydantic for settings management and validation.
"""

import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import List, Dict, Optional, Any
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Settings(BaseSettings):
    """
    Configuration settings with defaults and environment variable binding.
    Uses Pydantic for validation and environment variable binding.
    """
    # Base paths
    STORAGE_ROOT: str = Field(default="storage", env="STORAGE_ROOT")
    
    # Storage paths
    DOCUMENT_PATH: str = Field(default="storage/documents")
    PAGE_IMAGES_PATH: str = Field(default="storage/page_images")
    METADATA_PATH: str = Field(default="storage/metadata")
    TEMP_PATH: str = Field(default="storage/tmp")
    
    # Configurable subpaths for document statuses
    UNIQUE_DOCS_SUBPATH: str = Field(default="unique", env="UNIQUE_DOCS_SUBPATH")
    ARCHIVED_DOCS_SUBPATH: str = Field(default="archived", env="ARCHIVED_DOCS_SUBPATH") # Changed from "deduplicated" for consistency
    FLAGGED_DOCS_SUBPATH: str = Field(default="flagged_for_review", env="FLAGGED_DOCS_SUBPATH")
    
    # API settings
    HOST: str = Field(default="0.0.0.0", env="API_HOST")
    PORT: int = Field(default=8000, env="API_PORT")
    DEBUG: bool = Field(default=False, env="API_DEBUG")
    
    # Document analysis settings
    MIN_TEXT_LENGTH: int = Field(default=50)
    MAX_FILE_SIZE: int = Field(default=50 * 1024 * 1024)  # 50MB
    ALLOWED_EXTENSIONS: List[str] = Field(default=["pdf"])
    
    # Similarity thresholds
    DOC_SIMILARITY_THRESHOLD: float = Field(default=0.85, env="DOC_SIMILARITY_THRESHOLD")
    PAGE_SIMILARITY_THRESHOLD: float = Field(default=0.85, env="PAGE_SIMILARITY_THRESHOLD")
    MIN_SIMILAR_PAGES: int = Field(default=1, env="MIN_SIMILAR_PAGES")
    
    # Medical content detection
    MIN_MEDICAL_CONFIDENCE: float = Field(default=0.6, env="MIN_MEDICAL_CONFIDENCE")
    
    # Vector embedding settings
    SIMILARITY_METHOD: str = Field(default="tfidf", env="SIMILARITY_METHOD")
    # VECTOR_DIMENSION: int = Field(default=768)
    # EMBEDDING_MODEL: str = Field(default="all-MiniLM-L6-v2", env="EMBEDDING_MODEL")
    
    # Clustering settings
    CLUSTER_THRESHOLD: float = Field(default=0.75, env="CLUSTER_THRESHOLD")
    MIN_CLUSTER_SIZE: int = Field(default=2, env="MIN_CLUSTER_SIZE")
    
    # LSH settings
    LSH_JACCARD_THRESHOLD: float = Field(default=0.8, env="LSH_JACCARD_THRESHOLD")
    LSH_NUM_PERMUTATIONS: int = Field(default=128, env="LSH_NUM_PERMUTATIONS")
    
    # Celery / Redis settings
    REDIS_HOST: str = Field(default="localhost", env="REDIS_HOST")
    REDIS_PORT: int = Field(default=6379, env="REDIS_PORT")
    CELERY_BROKER_URL: Optional[str] = Field(default=None, env="CELERY_BROKER_URL")
    CELERY_RESULT_BACKEND: Optional[str] = Field(default=None, env="CELERY_RESULT_BACKEND")

    # Database settings
    DATABASE_URL: str = Field(default="sqlite:///./test.db", env="DATABASE_URL")
    
    # Processing limits
    MAX_BATCH_SIZE: int = Field(default=100, env="MAX_BATCH_SIZE")
    
    # OCR settings
    OCR_DPI: int = Field(default=300, env="OCR_DPI")
    OCR_LANGUAGE: str = Field(default="eng", env="OCR_LANGUAGE")
    
    # Thumbnail generation
    THUMBNAIL_SIZE: tuple = Field(default=(200, 200))
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


# Create global settings instance
settings = Settings()


def get_document_path(doc_id: str, status: str = "unique") -> str:
    """
    Get the path to a document file based on its ID and status.
    
    Args:
        doc_id: Document identifier
        status: Document status ("unique", "deduplicated", or "flagged_for_review")
        
    Returns:
        Path to the document file
    """
    base_path = os.path.join(settings.DOCUMENT_PATH, status)
    os.makedirs(base_path, exist_ok=True)
    return os.path.join(base_path, f"{doc_id}.pdf")


def get_page_image_path(doc_id: str, page_num: int) -> str:
    """
    Get the path to a page image file.
    
    Args:
        doc_id: Document identifier
        page_num: Page number
        
    Returns:
        Path to the page image file
    """
    os.makedirs(settings.PAGE_IMAGES_PATH, exist_ok=True)
    return os.path.join(settings.PAGE_IMAGES_PATH, f"{doc_id}_page{page_num}.png")


def get_metadata_path(filename: str) -> str:
    """
    Get the path to a metadata file.
    
    Args:
        filename: Metadata filename
        
    Returns:
        Path to the metadata file
    """
    os.makedirs(settings.METADATA_PATH, exist_ok=True)
    return os.path.join(settings.METADATA_PATH, filename)


def get_temp_path(filename: str) -> str:
    """
    Get the path to a temporary file.
    
    Args:
        filename: Temporary filename
        
    Returns:
        Path to the temporary file
    """
    os.makedirs(settings.TEMP_PATH, exist_ok=True)
    return os.path.join(settings.TEMP_PATH, filename)