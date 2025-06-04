# Medical PDF Deduplicator

A comprehensive system for detecting and managing duplicate medical PDFs.

## Overview

The Medical PDF Deduplicator is designed to help medical organizations manage document duplicates by:

- Detecting exact and near-duplicate documents
- Identifying duplicate pages within documents
- Analyzing medical content and specialties
- Providing clustering and topic analysis
- Supporting human review workflows

## Features

- **Document Comparison**: Compare two documents side-by-side with page analysis
- **Single Document Analysis**: Detect duplicate pages within a single document
- **Batch Folder Analysis**: Find duplicates across a folder of documents
- **Medical Content Analysis**: Detect medical terminology and specialties
- **Document Clustering**: Visualize relationships between documents
- **Content Analysis**: Extract topics and medical entities

## Architecture

The system consists of:

1. **Backend**: FastAPI Python application with ML-based similarity detection
2. **Frontend**: Next.js/React web interface with advanced visualization
3. **CLI Tools**: Command-line tools for batch processing

## Prerequisites

- Python 3.8+
- Node.js 14+
- PyTorch (for embeddings)
- Tesseract OCR (for image text extraction). Install the `tesseract-ocr` package and ensure the `tesseract` command is on your `PATH`.

## Installation

### Backend Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/medical-pdf-deduplicator.git
   cd medical-pdf-deduplicator
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure environment:
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```
   The `.env` file includes an `ENABLE_OCR` option to toggle OCR processing. Set it to `false` if Tesseract is not installed.

5. Create storage directories:
   ```bash
   mkdir -p storage/documents/unique
   mkdir -p storage/documents/deduplicated
   mkdir -p storage/documents/flagged_for_review
   mkdir -p storage/tmp
   mkdir -p storage/page_images
   mkdir -p storage/metadata
   mkdir -p storage/logs
   ```

### Frontend Setup

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Configure environment:
   ```bash
   cp .env.example .env.local
   # Edit .env.local with your settings
   ```

## Running the Application

### Start the Backend Server

```bash
cd backend
uvicorn backend.main:app --reload
```

### Start the Frontend Server

```bash
cd frontend
npm run dev
```

The application will be available at:
- Backend API: http://localhost:8000
- Frontend: http://localhost:3000
- API Documentation: http://localhost:8000/docs

### Document Upload Workflow

Uploading a document now triggers background processing using Celery. The `/upload` endpoint returns a JSON object containing the generated `doc_id` and the Celery `task_id`:

```json
{ "doc_id": "<document-id>", "task_id": "<celery-task-id>" }
```

Use the `doc_id` with `/documents/{doc_id}/analysis` to retrieve results once the task completes.

### Using the CLI Tools

The CLI provides several commands for document analysis:

```bash
# Compare two documents
pdf-dedupe compare file1.pdf file2.pdf

# Analyze a batch folder
pdf-dedupe batch folder_path

# Analyze a single document for internal duplicates
pdf-dedupe inspect document.pdf

# Start the web server
pdf-dedupe server
```

## License

MIT License

## Acknowledgements

- PyMuPDF for PDF processing
- Sentence-Transformers for text embeddings
- FastAPI for the backend framework
- Next.js and React for the frontend