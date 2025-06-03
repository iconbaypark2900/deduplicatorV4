"""
Intra-document analysis API endpoints.
Provides routes for analyzing similarities between pages within a single document.
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from fastapi.responses import FileResponse
from pdf2image import convert_from_path
import pytesseract
from PIL import Image, ImageDraw
import os
import tempfile
import uuid
import time
import logging
from typing import List, Tuple, Dict, Any, Set
from collections import defaultdict
from ingestion.preprocessing import measure_medical_confidence
from ingestion.pdf_reader import extract_pages_from_pdf
from similarity.tfidf import analyze_document_pages as tfidf_analyze_document_pages

# Create temporary directory for storing images
TEMP_DIR = os.path.abspath("storage/tmp")
os.makedirs(TEMP_DIR, exist_ok=True)
os.chmod(TEMP_DIR, 0o755)

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()


def cleanup_old_temp_files(temp_dir: str, max_age_hours: int = 1, preserve_files: set = None):
    """
    Clean up temporary files older than max_age_hours, preserving specified files.
    
    Args:
        temp_dir: Directory to clean up
        max_age_hours: Maximum age of files to keep in hours
        preserve_files: Set of filenames to preserve
    """
    if preserve_files is None:
        preserve_files = set()
        
    current_time = time.time()
    for filename in os.listdir(temp_dir):
        file_path = os.path.join(temp_dir, filename)
        if not os.path.isfile(file_path):
            continue
        if filename in preserve_files:
            continue
        if current_time - os.path.getmtime(file_path) > (max_age_hours * 3600):
            try:
                os.remove(file_path)
                logger.debug(f"Removed old temp file: {filename}")
            except Exception as e:
                logger.error(f"Failed to remove old temp file {filename}: {e}")


@router.get("/tmp/{filename}")
async def get_temp_image(filename: str):
    """
    Serve a temporary image file.
    
    Args:
        filename: Name of the image file
        
    Returns:
        Image file
        
    Raises:
        HTTPException: If image is not found
    """
    file_path = os.path.join(TEMP_DIR, filename)
    logger.debug(f"Attempting to serve image from: {file_path}")
    
    if not os.path.exists(file_path):
        logger.warning(f"File not found at: {file_path}")
        raise HTTPException(status_code=404, detail=f"Image not found: {filename}")
        
    return FileResponse(file_path)


def extract_words_with_boxes(image: Image.Image) -> List[Tuple[str, Tuple[int, int, int, int]]]:
    """
    Returns list of (word, (x, y, w, h)) tuples from OCR output.
    
    Args:
        image: PIL image to extract text from
        
    Returns:
        List of tuples containing (word, bounding_box)
    """
    # Ensure image is in RGB mode for OCR
    if image.mode != 'RGB':
        image = image.convert('RGB')
    
    # Configure Tesseract for better text detection
    custom_config = r'--oem 3 --psm 6 -l eng'  # Assume uniform text block
    data = pytesseract.image_to_data(image, config=custom_config, output_type=pytesseract.Output.DICT)
    
    words = []
    
    for i in range(len(data['text'])):
        word = data['text'][i].strip()
        conf = int(data['conf'][i])
        
        # Lower confidence threshold for better recall
        if conf > 30 and word:  # Lower threshold from 50 to 30
            # Use actual pixel coordinates
            bbox = (
                int(data['left'][i]),     # x
                int(data['top'][i]),      # y
                int(data['width'][i]),    # width
                int(data['height'][i])    # height
            )
            words.append((word, bbox))
    
    return words


def normalize_word(word: str) -> str:
    """
    Normalize word for comparison by removing punctuation and converting to lowercase.
    
    Args:
        word: Word to normalize
        
    Returns:
        Normalized word
    """
    return ''.join(c.lower() for c in word if c.isalnum())


def highlight_similar_words(
    image: Image.Image,
    words_to_highlight: Set[str],
    word_data: List[Tuple[str, Tuple[int, int, int, int]]]
) -> Image.Image:
    """
    Highlight similar words on the image.
    
    Args:
        image: PIL image to highlight
        words_to_highlight: Set of words to highlight
        word_data: List of (word, bbox) tuples
        
    Returns:
        PIL image with highlights
    """
    # Convert to RGBA for transparency
    if image.mode != 'RGBA':
        image = image.convert('RGBA')
    
    overlay = Image.new('RGBA', image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    
    # Normalize words to highlight
    normalized_words = set(normalize_word(word) for word in words_to_highlight)
    
    # Find words to highlight
    for word, bbox in word_data:
        if normalize_word(word) in normalized_words:
            x, y, w, h = bbox
            # Draw rectangle with padding
            padding = 2
            draw.rectangle(
                [(x-padding, y-padding), (x+w+padding, y+h+padding)],
                fill=(255, 255, 0, 100),  # Yellow with 40% opacity
                outline=(255, 165, 0, 200),  # Orange outline
                width=2
            )
    
    # Combine original image with overlay
    return Image.alpha_composite(image, overlay)


@router.post("/intra-document")
async def analyze_intra_document(
    file: UploadFile = File(...),
    threshold: float = Form(0.7)
):
    """
    Analyze a PDF document for internal similarities between pages using TF-IDF.
    Highlights are generated for pages found similar by TF-IDF.
    
    Args:
        file: PDF file to analyze
        threshold: Minimum TF-IDF similarity threshold (0-1)
        
    Returns:
        Dictionary with analysis results
        
    Raises:
        HTTPException: If analysis fails
    """
    try:
        logger.info(f"Starting intra-document analysis with TF-IDF threshold {threshold} for {file.filename}")
        
        temp_file_path = os.path.join(TEMP_DIR, f"{uuid.uuid4()}_{file.filename}")
        with open(temp_file_path, "wb") as f:
            f.write(await file.read())
        
        # 1. Extract text from all pages
        page_texts = extract_pages_from_pdf(temp_file_path)
        if not page_texts:
            os.unlink(temp_file_path)
            logger.warning(f"Could not extract any text from {file.filename}")
            raise HTTPException(status_code=400, detail="Could not extract text from document.")
        
        logger.info(f"Extracted text from {len(page_texts)} pages.")

        # 2. Initial images for all pages (non-highlighted)
        page_images_pil = convert_from_path(temp_file_path, dpi=300) # For targeted OCR later
        if len(page_images_pil) != len(page_texts):
            logger.warning(f"Mismatch between text page count ({len(page_texts)}) and image page count ({len(page_images_pil)}). Using lower count.")
            # Adjust to the minimum to prevent index errors, though this indicates a problem
            min_pages = min(len(page_texts), len(page_images_pil))
            page_texts = page_texts[:min_pages]
            page_images_pil = page_images_pil[:min_pages]
            if not min_pages:
                os.unlink(temp_file_path)
                raise HTTPException(status_code=500, detail="Failed to convert PDF pages to images consistently.")

        page_data_response = []
        preserved_files = set()
        for i, p_img in enumerate(page_images_pil):
            unique_id = str(uuid.uuid4())[:8]
            img_path = os.path.join(TEMP_DIR, f"page{i+1}_{unique_id}_orig.png")
            p_img.save(img_path, "PNG")
            preserved_files.add(os.path.basename(img_path))
            page_data_response.append({
                "pageNumber": i + 1,
                "imageUrl": f"/analyze/tmp/{os.path.basename(img_path)}", # Changed prefix to /analyze
                "ocrWordCount": 0 # Will be updated if OCR is done for highlighting
            })

        # 3. TF-IDF based similarity analysis
        # Note: tfidf_analyze_document_pages expects list of texts and returns 0-indexed pairs
        tfidf_similar_pairs = tfidf_analyze_document_pages(page_texts, threshold=threshold)
        logger.info(f"Found {len(tfidf_similar_pairs)} page pairs with TF-IDF similarity >= {threshold}")

        # 4. Targeted OCR and Highlighting for TF-IDF similar pairs
        highlighted_page_info = {} # Store info about highlighted pages: {page_num_1_based: new_url}

        for pair in tfidf_similar_pairs:
            idx1, idx2 = pair["page1_idx"], pair["page2_idx"]
            similarity_score = pair["similarity"]
            logger.info(f"Processing TF-IDF similar pair: Page {idx1+1} and Page {idx2+1} (Similarity: {similarity_score:.4f})")

            try:
                img1_pil = page_images_pil[idx1]
                img2_pil = page_images_pil[idx2]

                words_data1 = extract_words_with_boxes(img1_pil)
                words_data2 = extract_words_with_boxes(img2_pil)

                # Update OCR word count for these pages in page_data_response
                for p_data in page_data_response:
                    if p_data["pageNumber"] == idx1 + 1:
                        p_data["ocrWordCount"] = len(set(normalize_word(w) for w, _ in words_data1))
                    if p_data["pageNumber"] == idx2 + 1:
                        p_data["ocrWordCount"] = len(set(normalize_word(w) for w, _ in words_data2))

                common_words_for_highlight = set(normalize_word(w) for w, _ in words_data1).intersection(
                                           set(normalize_word(w) for w, _ in words_data2)
                                         )
                if not common_words_for_highlight:
                    logger.info(f"No common OCR words found between page {idx1+1} and {idx2+1} despite TF-IDF similarity.")
                    continue

                hl_img1 = highlight_similar_words(img1_pil.copy(), common_words_for_highlight, words_data1)
                hl_img2 = highlight_similar_words(img2_pil.copy(), common_words_for_highlight, words_data2)
                
                hl_unique_id = str(uuid.uuid4())[:8]
                hl_img_path1 = os.path.join(TEMP_DIR, f"page{idx1+1}_{hl_unique_id}_hl.png")
                hl_img_path2 = os.path.join(TEMP_DIR, f"page{idx2+1}_{hl_unique_id}_hl.png")
                
                hl_img1.save(hl_img_path1, "PNG")
                hl_img2.save(hl_img_path2, "PNG")
                preserved_files.add(os.path.basename(hl_img_path1))
                preserved_files.add(os.path.basename(hl_img_path2))

                highlighted_page_info[idx1 + 1] = f"/analyze/tmp/{os.path.basename(hl_img_path1)}"
                highlighted_page_info[idx2 + 1] = f"/analyze/tmp/{os.path.basename(hl_img_path2)}"
            except Exception as e_ocr:
                logger.error(f"Error during OCR/highlighting for pages {idx1+1}, {idx2+1}: {e_ocr}", exc_info=True)
                # Continue to next pair

        # Update image URLs in page_data_response if highlighted versions exist
        for p_data in page_data_response:
            if p_data["pageNumber"] in highlighted_page_info:
                p_data["imageUrl"] = highlighted_page_info[p_data["pageNumber"]]

        # 5. Medical Confidence
        medical_confidences = [measure_medical_confidence(text) for text in page_texts if text.strip()]
        avg_medical_confidence = sum(medical_confidences) / len(medical_confidences) if medical_confidences else 0.0

        # Clean up the original uploaded PDF file
        os.unlink(temp_file_path)
        cleanup_old_temp_files(TEMP_DIR, max_age_hours=1, preserve_files=preserved_files)
        
        # Prepare final highSimilarityPairs with 1-based indexing
        final_high_similarity_pairs = [
            {"page1": pair["page1_idx"] + 1, "page2": pair["page2_idx"] + 1, "similarity": pair["similarity"]}
            for pair in tfidf_similar_pairs
        ]
        final_high_similarity_pairs.sort(key=lambda x: x["similarity"], reverse=True)

        return {
            "filename": file.filename,
            "pages": page_data_response,
            # "similarityMatrix": [], # Removed as it was Jaccard based and computationally intensive for all pairs
            "highSimilarityPairs": final_high_similarity_pairs, # TF-IDF based pairs
            "medicalConfidence": round(avg_medical_confidence, 4)
        }
        
    except HTTPException: # Re-raise HTTPExceptions directly
        raise
    except Exception as e:
        # Log the specific error before raising a generic one
        logger.error(f"Intra-document analysis failed for {file.filename}: {str(e)}", exc_info=True)
        # Clean up temp file in case of failure before unlinking
        if 'temp_file_path' in locals() and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except Exception as e_clean:
                logger.error(f"Failed to cleanup temp file {temp_file_path} on error: {e_clean}")
        raise HTTPException(status_code=500, detail=f"Intra-document analysis failed: {str(e)}") 