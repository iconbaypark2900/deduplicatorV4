"""
Main FastAPI application for the Medical PDF Deduplicator system.
Creates and configures the FastAPI app with all routes and middleware.
"""

import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Import API routes
from backend.api.upload import router as upload_router
from backend.api.compare import router as compare_router
from backend.api.documents import router as documents_router
from backend.api.page import router as page_router
from backend.api.data_science import router as data_science_router

# Create the FastAPI application
app = FastAPI(
    title="Medical PDF Deduplicator",
    description="A system for detecting and managing duplicate medical PDFs",
    version="1.0.0"
)

# Configure CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this to your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure storage directories exist
os.makedirs("storage/documents", exist_ok=True)
os.makedirs("storage/tmp", exist_ok=True)
os.makedirs("storage/page_images", exist_ok=True)
os.makedirs("storage/metadata", exist_ok=True)

# Include routers
app.include_router(upload_router, prefix="/upload")
app.include_router(compare_router, prefix="/compare")
app.include_router(documents_router, prefix="/documents")
app.include_router(page_router, prefix="/page")
app.include_router(data_science_router, prefix="/data-science")

# Mount static file directories for serving images and temp files
app.mount("/images", StaticFiles(directory="storage/page_images"), name="images")
app.mount("/temp", StaticFiles(directory="storage/tmp"), name="temp")

@app.get("/")
async def root():
    """
    Root endpoint for the API.
    Returns basic info about the service.
    """
    return {
        "service": "Medical PDF Deduplicator API",
        "version": "1.0.0",
        "status": "running"
    }

@app.get("/health")
async def health_check():
    """
    Health check endpoint for the API.
    Used for monitoring and uptime checks.
    """
    return {"status": "healthy"}

# Serve document files
@app.get("/documents/{doc_id}")
async def serve_document(doc_id: str):
    """
    Serve a document file given its ID.
    
    Args:
        doc_id: Document identifier
        
    Returns:
        PDF file
        
    Raises:
        HTTPException: If document is not found
    """
    # Check unique documents first
    doc_path = f"storage/documents/unique/{doc_id}.pdf"
    if os.path.exists(doc_path):
        return FileResponse(doc_path)
    
    # Then check deduplicated documents
    doc_path = f"storage/documents/deduplicated/{doc_id}.pdf"
    if os.path.exists(doc_path):
        return FileResponse(doc_path)
    
    # Finally check flagged documents
    doc_path = f"storage/documents/flagged_for_review/{doc_id}.pdf"
    if os.path.exists(doc_path):
        return FileResponse(doc_path)
    
    raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)