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
import numpy as np
from collections import defaultdict
from ingestion.preprocessing import measure_medical_confidence

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


def calculate_similarity_score(words1_set: Set[str], words2_set: Set[str]) -> float:
    """
    Calculate Jaccard similarity between two sets of words.
    
    Args:
        words1_set: First set of words
        words2_set: Second set of words
        
    Returns:
        Similarity score between 0 and 1
    """
    if not words1_set or not words2_set:
        return 0.0
        
    intersection = len(words1_set.intersection(words2_set))
    union = len(words1_set.union(words2_set))
    
    return intersection / union if union > 0 else 0.0


@router.post("/intra-document")
async def analyze_intra_document(
    file: UploadFile = File(...),
    threshold: float = Form(0.7)
):
    """
    Analyze a PDF document for internal similarities between pages.
    
    Args:
        file: PDF file to analyze
        threshold: Minimum similarity threshold (0-1)
        
    Returns:
        Dictionary with analysis results
        
    Raises:
        HTTPException: If analysis fails
    """
    try:
        logger.info(f"Starting intra-document analysis with threshold {threshold}")
        
        # Save uploaded file temporarily
        file_path = os.path.join(TEMP_DIR, file.filename)
        with open(file_path, "wb") as f:
            f.write(await file.read())
        
        # Convert PDF to images
        logger.debug("Converting PDF to images")
        pages = convert_from_path(file_path, dpi=300)
        logger.info(f"Converted {len(pages)} pages")
        
        # Extract text and normalized words from each page
        page_data = []
        page_words = []
        page_texts = []  # Store extracted text for medical analysis
        preserved_files = set()
        
        for i, page in enumerate(pages):
            logger.debug(f"Processing page {i+1}")
            
            # Extract words and their positions
            words_with_boxes = extract_words_with_boxes(page)
            
            # Get normalized words as a set
            words_set = set(normalize_word(word) for word, _ in words_with_boxes)
            
            # Extract full text from the page for medical analysis
            page_text = " ".join(word for word, _ in words_with_boxes)
            page_texts.append(page_text)
            
            # Save original page image
            unique_id = str(uuid.uuid4())[:8]
            img_path = os.path.join(TEMP_DIR, f"page{i+1}_{unique_id}.png")
            page.save(img_path, "PNG")
            preserved_files.add(os.path.basename(img_path))
            
            # Store page data
            page_data.append({
                "pageNumber": i + 1,
                "imageUrl": f"/temp/{os.path.basename(img_path)}",
                "wordCount": len(words_set)
            })
            
            # Store normalized words for similarity calculation
            page_words.append({
                "pageNumber": i + 1,
                "words": words_set,
                "wordBoxes": words_with_boxes
            })
        
        # Calculate similarity matrix
        similarity_matrix = []
        high_similarity_pairs = []
        
        for i, page1 in enumerate(page_words):
            for j, page2 in enumerate(page_words):
                if i < j:  # Only compute upper triangle to avoid duplicates
                    similarity = calculate_similarity_score(page1["words"], page2["words"])
                    
                    # Store in matrix
                    similarity_matrix.append({
                        "page1": page1["pageNumber"],
                        "page2": page2["pageNumber"],
                        "similarity": round(similarity, 4)
                    })
                    
                    # If similarity exceeds threshold, mark as high similarity
                    if similarity >= threshold:
                        logger.info(f"High similarity found: Page {page1['pageNumber']} and Page {page2['pageNumber']} - {similarity:.4f}")
                        high_similarity_pairs.append({
                            "page1": page1["pageNumber"],
                            "page2": page2["pageNumber"],
                            "similarity": round(similarity, 4)
                        })
                        
                        # Highlight similar content on both pages
                        common_words = page1["words"].intersection(page2["words"])
                        
                        # Get both page images
                        original_page1 = pages[i].convert('RGBA')
                        original_page2 = pages[j].convert('RGBA')
                        
                        # Highlight common words
                        highlighted_page1 = highlight_similar_words(
                            original_page1, common_words, page1["wordBoxes"]
                        )
                        highlighted_page2 = highlight_similar_words(
                            original_page2, common_words, page2["wordBoxes"]
                        )
                        
                        # Save highlighted images
                        highlighted_id = str(uuid.uuid4())[:8]
                        img_path1 = os.path.join(TEMP_DIR, f"page{page1['pageNumber']}_hl_{highlighted_id}.png")
                        img_path2 = os.path.join(TEMP_DIR, f"page{page2['pageNumber']}_hl_{highlighted_id}.png")
                        
                        highlighted_page1.save(img_path1, "PNG")
                        highlighted_page2.save(img_path2, "PNG")
                        
                        preserved_files.add(os.path.basename(img_path1))
                        preserved_files.add(os.path.basename(img_path2))
                        
                        # Update page URLs to the highlighted versions for these pages
                        for p in page_data:
                            if p["pageNumber"] == page1["pageNumber"]:
                                p["imageUrl"] = f"/temp/{os.path.basename(img_path1)}"
                            elif p["pageNumber"] == page2["pageNumber"]:
                                p["imageUrl"] = f"/temp/{os.path.basename(img_path2)}"
        
        # Clean up the original PDF file
        os.unlink(file_path)
        cleanup_old_temp_files(TEMP_DIR, max_age_hours=1, preserve_files=preserved_files)
        
        # Sort high similarity pairs by similarity (descending)
        high_similarity_pairs.sort(key=lambda x: x["similarity"], reverse=True)
        
        # Calculate medical confidence
        medical_confidences = [measure_medical_confidence(text) for text in page_texts if text.strip()]
        avg_medical_confidence = sum(medical_confidences) / len(medical_confidences) if medical_confidences else 0.0
        
        return {
            "filename": file.filename,
            "pages": page_data,
            "similarityMatrix": similarity_matrix,
            "highSimilarityPairs": high_similarity_pairs,
            "medicalConfidence": round(avg_medical_confidence, 4)
        }
        
    except Exception as e:
        logger.error(f"Intra-document analysis failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {e}") 