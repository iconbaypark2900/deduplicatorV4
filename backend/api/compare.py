"""
Document comparison API endpoints.
Provides routes for comparing documents and visualizing differences.
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from fastapi.responses import FileResponse
from backend.services.extractor import extract_text_and_pages
from similarity.embedding import embed_text
from similarity.search import compute_similarity
from backend.services.diff_utils import compute_text_diff, compute_changed_bounding_boxes
from pdf2image import convert_from_path
import pytesseract
from PIL import Image, ImageDraw
import os
import tempfile
import uuid
import time
import logging
from typing import List, Tuple, Dict, Any

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
    logger.debug(f"Processing OCR data with {len(data['text'])} elements")
    
    for i in range(len(data['text'])):
        word = data['text'][i].strip()
        conf = int(data['conf'][i])
        
        # Lower confidence threshold for better recall
        if conf > 30 and word:  # Lower threshold from 50 to 30
            logger.debug(f"Found word '{word}' with confidence {conf}")
            # Use actual pixel coordinates
            bbox = (
                int(data['left'][i]),     # x
                int(data['top'][i]),      # y
                int(data['width'][i]),    # width
                int(data['height'][i])    # height
            )
            words.append((word, bbox))
    
    logger.debug(f"Extracted {len(words)} words from image")
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


def group_boxes(word_data: List[Tuple[str, Tuple[int, int, int, int]]], words_to_highlight: set) -> List[List[Tuple[int, int, int, int]]]:
    """
    Group adjacent word boxes into larger regions.
    
    Args:
        word_data: List of (word, bbox) tuples
        words_to_highlight: Set of words to highlight
        
    Returns:
        List of lists of bounding boxes
    """
    groups = []
    current_group = []
    
    for word, bbox in word_data:
        if normalize_word(word) in words_to_highlight:
            if not current_group:
                current_group.append(bbox)
            else:
                last_bbox = current_group[-1]
                # Check if current word is adjacent to the last word
                if abs(bbox[0] - (last_bbox[0] + last_bbox[2])) < 50:  # 50 pixels threshold
                    current_group.append(bbox)
                else:
                    if current_group:
                        groups.append(current_group)
                    current_group = [bbox]
        else:
            if current_group:
                groups.append(current_group)
            current_group = []
    
    if current_group:
        groups.append(current_group)
    
    return groups


def highlight_words_on_image(image: Image.Image, words_to_highlight: set, word_data: List[Tuple[str, Tuple[int, int, int, int]]]) -> Image.Image:
    """
    Draw highlights directly on the image for the specified words.
    
    Args:
        image: PIL image to highlight
        words_to_highlight: Set of words to highlight
        word_data: List of (word, bbox) tuples
        
    Returns:
        PIL image with highlights
    """
    # Ensure image is in RGBA mode
    if image.mode != 'RGBA':
        image = image.convert('RGBA')
    
    draw = ImageDraw.Draw(image, 'RGBA')
    words_to_highlight = set(normalize_word(word) for word in words_to_highlight)
    
    logger.debug(f"Words to highlight: {words_to_highlight}")
    logger.debug(f"Word data length: {len(word_data)}")
    
    # Group adjacent word boxes
    groups = group_boxes(word_data, words_to_highlight)
    logger.debug(f"Found {len(groups)} groups of similar text")
    
    highlighted_count = 0
    for group in groups:
        if not group:
            continue
            
        # Calculate the bounding box for the entire group
        min_x = min(bbox[0] for bbox in group)
        min_y = min(bbox[1] for bbox in group)
        max_x = max(bbox[0] + bbox[2] for bbox in group)
        max_y = max(bbox[1] + bbox[3] for bbox in group)
        
        # Add padding
        padding = 5
        min_x -= padding
        min_y -= padding
        max_x += padding
        max_y += padding
        
        # Draw highlight for the group
        overlay = Image.new('RGBA', image.size, (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        overlay_draw.rectangle(
            [(min_x, min_y), (max_x, max_y)],
            fill=(255, 0, 0, 128),     # Red with 50% opacity
            outline=(255, 0, 0, 255),  # Solid red outline
            width=2
        )
        image = Image.alpha_composite(image, overlay)
        highlighted_count += 1
    
    logger.debug(f"Highlighted {highlighted_count} groups of similar text")
    return image


def calculate_similarity_score(words1_set: set, words2_set: set) -> float:
    """
    Calculate similarity score between two sets of words.
    
    Args:
        words1_set: First set of words
        words2_set: Second set of words
        
    Returns:
        Jaccard similarity score (0-1)
    """
    intersection = len(words1_set.intersection(words2_set))
    union = len(words1_set.union(words2_set))
    return intersection / union if union > 0 else 0.0


@router.post("/")
async def compare_documents(
    file1: UploadFile = File(...),
    file2: UploadFile = File(...)
) -> Dict[str, Any]:
    """
    Compare two PDF documents and highlight similarities.
    
    Args:
        file1: First PDF file
        file2: Second PDF file
        
    Returns:
        Dictionary with comparison results
        
    Raises:
        HTTPException: If comparison fails
    """
    try:
        logger.debug("Starting document comparison")
        # Save uploaded files temporarily
        path1 = os.path.join(TEMP_DIR, file1.filename)
        path2 = os.path.join(TEMP_DIR, file2.filename)
        
        with open(path1, "wb") as f:
            f.write(await file1.read())
        with open(path2, "wb") as f:
            f.write(await file2.read())

        logger.debug("Converting PDFs to images")
        # Convert PDFs to images with higher DPI for better OCR
        pages1 = convert_from_path(path1, dpi=300)
        pages2 = convert_from_path(path2, dpi=300)

        logger.debug(f"Processing {len(pages1)} pages from first document")
        logger.debug(f"Processing {len(pages2)} pages from second document")

        doc1_pages = []
        doc2_pages = []
        total_similarity = 0.0
        total_pages = 0
        preserved_files = set()  # Track files to preserve

        # Process each page
        for i, (page1, page2) in enumerate(zip(pages1, pages2)):
            logger.debug(f"Processing page {i+1}")
            
            # Convert to RGB if needed
            if page1.mode != 'RGB':
                page1 = page1.convert('RGB')
            if page2.mode != 'RGB':
                page2 = page2.convert('RGB')
            
            # Get OCR words and their positions
            words1 = extract_words_with_boxes(page1)
            words2 = extract_words_with_boxes(page2)
            
            # Get normalized words from each page
            words1_set = set(normalize_word(word) for word, _ in words1)
            words2_set = set(normalize_word(word) for word, _ in words2)
            
            # Calculate page similarity
            page_similarity = calculate_similarity_score(words1_set, words2_set)
            total_similarity += page_similarity
            total_pages += 1
            
            logger.debug(f"Page {i+1} similarity: {page_similarity:.2f}")
            
            # Find common words (similarities)
            common = words1_set.intersection(words2_set)
            
            logger.debug(f"Page {i+1} common words: {len(common)}")
            logger.debug(f"Sample common words: {list(common)[:5]}")
            
            # Convert images to RGBA for highlighting
            page1_rgba = page1.convert('RGBA')
            page2_rgba = page2.convert('RGBA')
            
            # Highlight common words on images
            highlighted1 = highlight_words_on_image(page1_rgba, common, words1)
            highlighted2 = highlight_words_on_image(page2_rgba, common, words2)
            
            # Save highlighted images
            unique_id = str(uuid.uuid4())[:8]
            img_path1 = os.path.join(TEMP_DIR, f"doc1_page{i}_{unique_id}.png")
            img_path2 = os.path.join(TEMP_DIR, f"doc2_page{i}_{unique_id}.png")
            highlighted1.save(img_path1, "PNG")
            highlighted2.save(img_path2, "PNG")
            
            # Add to preserved files
            preserved_files.add(os.path.basename(img_path1))
            preserved_files.add(os.path.basename(img_path2))
            
            doc1_pages.append({
                "pageNumber": i + 1,
                "imageUrl": f"/compare/tmp/{os.path.basename(img_path1)}",
                "similarity": round(page_similarity, 4)
            })
            
            doc2_pages.append({
                "pageNumber": i + 1,
                "imageUrl": f"/compare/tmp/{os.path.basename(img_path2)}",
                "similarity": round(page_similarity, 4)
            })

        # Calculate overall similarity
        overall_similarity = total_similarity / total_pages if total_pages > 0 else 0.0
        logger.debug(f"Overall document similarity: {overall_similarity:.2f}")

        # Clean up only the PDF files, preserve the processed images
        os.unlink(path1)
        os.unlink(path2)
        cleanup_old_temp_files(TEMP_DIR, max_age_hours=1, preserve_files=preserved_files)

        return {
            "doc1": {
                "text": "Highlighted similarities shown in images",
                "filename": file1.filename,
                "pages": doc1_pages
            },
            "doc2": {
                "text": "Highlighted similarities shown in images",
                "filename": file2.filename,
                "pages": doc2_pages
            },
            "similarity": round(overall_similarity, 4)  # Overall document similarity
        }

    except Exception as e:
        logger.error(f"Comparison failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Comparison failed: {e}")