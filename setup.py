#!/usr/bin/env python3
"""
Script to set up the Medical PDF Deduplicator project structure.
Creates all necessary directories and empty files.
"""

import os
import sys
from pathlib import Path

def create_directory(path):
    """Create directory if it doesn't exist."""
    Path(path).mkdir(parents=True, exist_ok=True)
    print(f"Created directory: {path}")

def create_file(path):
    """Create an empty file if it doesn't exist."""
    file_path = Path(path)
    if not file_path.exists():
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.touch()
        print(f"Created file: {path}")
    else:
        print(f"File already exists: {path}")

def setup_project():
    """Set up the entire project structure."""
    # Create main directories
    dirs = [
        # Backend directories
        "backend",
        "backend/api",
        "backend/models",
        "backend/services",
        
        # CLI directories
        "cli",
        
        # Frontend directories
        "frontend",
        "frontend/app",
        "frontend/components",
        "frontend/components/analysis",
        "frontend/components/core",
        "frontend/components/data-science",
        "frontend/components/review",
        "frontend/services",
        "frontend/types",
        
        # Core modules
        "ingestion",
        "similarity",
        "utils",
        
        # Storage directories
        "storage",
        "storage/documents",
        "storage/documents/deduplicated",
        "storage/documents/flagged_for_review",
        "storage/documents/unique",
        "storage/logs",
        "storage/metadata",
        "storage/page_images",
        "storage/tmp",
    ]
    
    for dir_path in dirs:
        create_directory(dir_path)
    
    # Create backend files
    backend_files = [
        "backend/__init__.py",
        "backend/main.py",
        "backend/api/__init__.py",
        "backend/api/compare.py",
        "backend/api/data_science.py",
        "backend/api/documents.py",
        "backend/api/page.py",
        "backend/api/upload.py",
        "backend/models/__init__.py",
        "backend/models/schemas.py",
        "backend/services/__init__.py",
        "backend/services/deduplicator.py",
        "backend/services/diff_utils.py",
        "backend/services/extractor.py",
        "backend/services/logger.py",
        "backend/services/rebuilder.py",
    ]
    
    for file_path in backend_files:
        create_file(file_path)
    
    # Create CLI files
    cli_files = [
        "cli/__init__.py",
        "cli/batch_folder.py",
        "cli/doc_comparator.py",
        "cli/intra_doc_inspector.py",
        "cli/main.py",
    ]
    
    for file_path in cli_files:
        create_file(file_path)
    
    # Create frontend files
    frontend_files = [
        "frontend/app/page.tsx",
        "frontend/app/layout.tsx",
        "frontend/components/analysis/BatchFolder.tsx",
        "frontend/components/analysis/DocumentComparison.tsx",
        "frontend/components/analysis/SingleDocument.tsx",
        "frontend/components/core/Navigation.tsx",
        "frontend/components/core/UploadDropzone.tsx",
        "frontend/components/data-science/ContentAnalysis.tsx",
        "frontend/components/data-science/DocumentClustering.tsx",
        "frontend/components/data-science/MedicalAnalysis.tsx",
        "frontend/components/review/Review.tsx",
        "frontend/services/baseApi.ts",
        "frontend/services/dataScienceService.ts",
        "frontend/services/documentService.ts",
        "frontend/types/document.ts",
        "frontend/types/review.ts",
    ]
    
    for file_path in frontend_files:
        create_file(file_path)
    
    # Create ingestion files
    ingestion_files = [
        "ingestion/__init__.py",
        "ingestion/pdf_reader.py",
        "ingestion/preprocessing.py",
    ]
    
    for file_path in ingestion_files:
        create_file(file_path)
    
    # Create similarity files
    similarity_files = [
        "similarity/__init__.py",
        "similarity/embedding.py",
        "similarity/engine.py",
        "similarity/hashing.py",
        "similarity/search.py",
        "similarity/tfidf.py",
        "similarity/vectorization.py",
    ]
    
    for file_path in similarity_files:
        create_file(file_path)
    
    # Create utils files
    utils_files = [
        "utils/__init__.py",
        "utils/config.py",
        "utils/duplicate_analysis.py",
        "utils/page_tracker.py",
    ]
    
    for file_path in utils_files:
        create_file(file_path)
    
    # Create root files
    root_files = [
        ".env.example",
        ".gitignore",
        "README.md",
        "requirements.txt",
        "setup.py",
    ]
    
    for file_path in root_files:
        create_file(file_path)
    
    print("\nProject structure setup completed successfully!")

if __name__ == "__main__":
    setup_project()