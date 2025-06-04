# Project Refactoring and Enhancement Plan: agents.md

This document outlines the key pending tasks for refactoring and enhancing the PDF deduplication system.

## 1. Fix: Implement Asynchronous Main Document Upload Pipeline

### Problem Statement:
The main document upload endpoint (`/upload`) in `backend/api/upload.py` currently processes documents synchronously. This means the HTTP request remains open until all processing (text extraction, hashing, LSH, TF-IDF, database operations) is complete. For larger documents or high load, this can lead to long request times, client timeouts, and poor scalability.

### Proposed Fix:
Refactor the `/upload` endpoint to handle file uploads asynchronously using Celery.

1.  **API Endpoint (`backend/api/upload.py`):**
    * The `upload_document` function will:
        * Quickly validate the uploaded file (e.g., ensure it's a PDF).
        * Generate a unique `doc_id`.
        * Save the uploaded file to a temporary, shared location accessible by Celery workers (e.g., within `settings.TEMP_PATH`).
        * Dispatch the `process_document_task` Celery task (defined in `backend/tasks/pipeline_tasks.py`), passing the path to the temporary file, original filename, and the `doc_id`.
        * Immediately return a response to the client containing the `doc_id` and the Celery `task_id`.

2.  **Response Model (`backend/models/schemas.py`):**
    * Create a new Pydantic model, for example, `AsyncUploadResponse`, to define the structure of the immediate response from the asynchronous upload endpoint (e.g., `{"message": "File queued for processing", "doc_id": "...", "task_id": "..."}`).

3.  **Celery Task (`backend/tasks/pipeline_tasks.py`):**
    * The existing `process_document_task` already calls the `PipelineOrchestrator`. This task will now be the primary worker for document processing.

4.  **Temporary File Cleanup (`backend/services/pipeline_orchestrator.py`):**
    * The `PipelineOrchestrator.process_document` method receives the `pdf_path` (which is the temporary path where the API saved the file). After it has copied the file to its persistent storage location, it should ensure the original temporary file at `pdf_path` is deleted, typically in a `finally` block.

### Files to Modify:
* `backend/api/upload.py` (Main logic for the endpoint change)
* `backend/models/schemas.py` (Add `AsyncUploadResponse`)
* `backend/services/pipeline_orchestrator.py` (Ensure robust cleanup of the temporary input file)
* `backend/tasks/pipeline_tasks.py` (Verify it correctly receives parameters and updates task state)

### Impact:
* Improves UI responsiveness significantly for document uploads.
* Enhances system scalability by offloading heavy processing to background workers.
* Allows clients to poll for task status using the `task_id`.

---

## 2. Fix: Integrate Conditional OCR into Core Text Extraction

### Problem Statement:
The current text extraction in `ingestion/pdf_reader.py`, primarily using `fitz` (PyMuPDF), is efficient for text-based PDFs. However, it may yield little to no text for scanned (image-based) PDF pages or pages that are predominantly images containing text. This leads to poor data quality for subsequent analysis stages (TF-IDF, LSH, etc.) for such documents.

### Proposed Fix:
Enhance the `extract_page_text` function within `ingestion/pdf_reader.py` to conditionally perform Optical Character Recognition (OCR) using `pytesseract` when direct text extraction is insufficient.

1.  **Modify `extract_page_text` in `ingestion/pdf_reader.py`:**
    * The function should first attempt to extract text using `page.get_text("text")`.
    * If the extracted text is empty or below a certain minimal threshold (e.g., very few characters), and an `attempt_ocr` flag is true (should be default):
        * The PDF page (`fitz.Page` object) should be rendered into an image (e.g., PNG) using `page.get_pixmap(dpi=settings.OCR_DPI)`.
        * This image should be converted into a `PIL.Image` object.
        * `pytesseract.image_to_string()` should be called on the `PIL.Image` object, using the language specified in `settings.OCR_LANGUAGE`.
        * If the OCR process yields substantial text, this text should be used as the extracted text for the page.
        * Proper error handling for the OCR process should be included.
    * If OCR is not attempted or fails to yield substantial text, the function can proceed with its existing fallback mechanisms (`page.get_text("html")`, etc.).

2.  **Update Calling Functions:**
    * Functions like `extract_text_from_pdf` and `extract_pages_from_pdf` within `ingestion/pdf_reader.py` should be updated to call the enhanced `extract_page_text`, ensuring parameters like `ocr_dpi` and `ocr_lang` (sourced from `utils.config.settings`) are passed down.

3.  **Dependencies and Configuration:**
    * Ensure `Pillow` and `pytesseract` are in `requirements.txt`.
    * Ensure `settings.OCR_DPI` and `settings.OCR_LANGUAGE` are defined in `utils/config.py`.
    * Tesseract OCR engine must be installed on the system where the backend/Celery workers run.

### Files to Modify:
* `ingestion/pdf_reader.py` (Primary location for all changes)
* `utils/config.py` (Ensure `OCR_DPI` and `OCR_LANGUAGE` settings are present and appropriate)

### Impact:
* Significantly improves text extraction quality for scanned or image-heavy PDFs.
* Provides more comprehensive input data for all downstream analysis tasks (hashing, LSH, TF-IDF, intra-document analysis).
* Makes the entire system more robust in handling diverse PDF types.

---

## 3. Fix: Finalize Intra-Document Analysis Feature Workflow & Persistence

### Problem Statement:
The intra-document analysis feature (currently in `backend/api/analyze.py`) provides valuable page-to-page similarity insights within a single document. However, its current workflow (Option 1: on-the-fly analysis of a new upload) is somewhat disconnected from the main document ingestion pipeline and database. Its findings are not automatically persisted in a structured way that relates to the main database entities. For better integration, we are considering Option 3: on-demand analysis of already processed documents.

### Proposed Fix (Focusing on Option 3 for Better Integration):
Refactor the intra-document analysis feature to operate on documents already ingested and processed by the main pipeline, leveraging the centralized database.

1.  **Modify/Create API Endpoint:**
    * The current `/analyze/intra-document` endpoint in `backend/api/analyze.py` (which accepts a file upload) will be refactored, or a new endpoint will be created (e.g., `GET /documents/{doc_id}/analyze-internal-pages`).
    * This endpoint will now accept a `doc_id` as a path parameter.

2.  **Backend Logic (`backend/api/analyze.py` or new service):**
    * On receiving a `doc_id`:
        * Fetch all page texts for this `doc_id` from the `Page` table in the database (via `utils.database.get_pages_by_document_id` or a similar function that retrieves full page text). These texts would have already benefited from the OCR upgrades during their initial ingestion by the main pipeline.
        * Perform the TF-IDF based page-to-page similarity analysis (e.g., using `similarity.tfidf.analyze_document_pages`) on these retrieved page texts.
        * Return the identified similar page pairs and their similarity scores.
        * The mechanism for displaying page images can leverage existing `Page.page_image_path` or relevant endpoints in `backend/api/page.py`.

3.  **Database Schema and Persistence (Consideration):**
    * **Page Text Storage:** Crucially, ensure the `Page` table (defined in `utils/database.py`) stores sufficient text for each page for effective TF-IDF analysis. The current `text_snippet` may be too short. Consider adding a `full_page_text` column to the `Page` model and ensure the `process_document_pages` function in `utils/page_tracker.py` populates this new field during the main document ingestion pipeline.
    * **Storing Findings:** Implement a mechanism to persist the TF-IDF based page-pair similarities identified by this feature.
        * These relationships can be stored in the existing `PageDuplicate` table. The `source_page_id` and `duplicate_page_id` would refer to pages within the same `document_id`, and the `similarity` column would store the TF-IDF score.
        * This would likely involve an API endpoint (perhaps triggered by a "Save Analysis Results" button in the review UI for this feature) to write these findings to the database.

4.  **Frontend Changes:**
    * The UI component for intra-document analysis (`frontend/components/analysis/IntraDocumentComparison.tsx`) would need to be updated. Instead of an upload dropzone, it should allow users to select or input a `doc_id` of an existing document.
    * `frontend/services/documentService.ts` would require a corresponding new function to call the refactored backend API endpoint.

## Files to Modify (for Option 3):
* `backend/api/analyze.py` (Refactor existing endpoint or create a new one that takes `doc_id`).
* `utils/database.py` (Add `full_page_text` to `Page` model; ensure `PageDuplicate` schema is suitable).
* `utils/page_tracker.py` (Update `process_document_pages` to populate `full_page_text` if added).
* `frontend/components/analysis/IntraDocumentComparison.tsx` (Change UI from file upload to `doc_id` input/selection).
* `frontend/services/documentService.ts` (Update or add service call for the new/refactored API).
* Possibly new API endpoints for persisting the intra-document analysis results if not combined with existing review mechanisms.

## Impact:
* Aligns the intra-document analysis feature more closely with the database-centric architecture.
* Leverages consistently processed and OCR-enhanced page texts from the main pipeline.
* Avoids redundant text extraction for documents already in the system.
* Provides a clearer path for persisting the detailed intra-document similarity findings into the main database, making them queryable and part of the holistic document view.
* If Option 1 (on-the-fly analysis of new uploads) is still desired as a separate utility, it could be maintained as a distinct endpoint, while this Option 3 provides the more integrated solution.