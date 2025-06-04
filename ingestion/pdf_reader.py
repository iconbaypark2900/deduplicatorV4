"""
PDF text extraction utilities.
Provides functions for extracting text from PDF documents.
"""

import os
import io
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
from tenacity import retry, stop_after_attempt, wait_fixed
from typing import List, Optional, Generator, Dict
import logging
from ingestion.preprocessing import normalize_medical_text
from utils.config import settings

# Configure logging
logger = logging.getLogger(__name__)


def extract_page_text(
    page: fitz.Page,
    ocr_dpi: int = settings.OCR_DPI,
    attempt_ocr: bool = True,
    min_length: int = settings.MIN_TEXT_LENGTH,
) -> str:
    """
    Try different text extraction methods to get content from a page.
    
    Args:
        page: PDF page object
        
    Returns:
        Extracted text from the page
    """
    modes = ["text", "html", "json", "raw"]
    text = ""
    for mode in modes:
        if mode != "text":
            logger.debug(f"{mode.upper()} mode{' (fallback)' if text.strip() else ''}")
        text = page.get_text(mode)

        if attempt_ocr and len(text.strip()) < min_length:
            try:
                pix = page.get_pixmap(dpi=ocr_dpi)
                img_bytes = pix.tobytes("png")
                image = Image.open(io.BytesIO(img_bytes))
                ocr_text = pytesseract.image_to_string(image, lang=settings.OCR_LANGUAGE)
                if len(ocr_text.strip()) > len(text.strip()):
                    text = ocr_text
            except Exception as e:
                logger.error(
                    f"OCR failed on page {page.number + 1 if hasattr(page, 'number') else ''}: {e}"
                )
        if len(text.strip()) >= min_length:
            break

    return text


@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
def extract_text_from_pdf(
    pdf_path: str,
    ocr_dpi: int = settings.OCR_DPI,
    attempt_ocr: bool = settings.ENABLE_OCR,
    min_length: int = settings.MIN_TEXT_LENGTH,
) -> str:
    """
    Extract and normalize text from entire PDF file.
    
    Args:
        pdf_path: Path to the PDF file
        ocr_dpi: DPI setting when performing OCR on image-based pages
        
    Returns:
        Normalized text from the PDF
        
    Raises:
        Exception: If text extraction fails
    """
    try:
        doc = fitz.open(pdf_path)
        texts = []
        
        for page in doc:
            text = extract_page_text(
                page,
                ocr_dpi=ocr_dpi,
                attempt_ocr=attempt_ocr,
                min_length=min_length,
            )
            if text.strip():
                texts.append(text)
            else:
                logger.warning(f"No text extracted from page {page.number + 1}")
                
        doc.close()
        
        full_text = " ".join(texts)
        if not full_text.strip():
            logger.error("No text extracted from any page")
            return ""
            
        return normalize_medical_text(full_text)
        
    except Exception as e:
        logger.error(f"Failed to extract text from {pdf_path}: {e}", exc_info=True)
        raise


@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
def extract_pages_from_pdf(
    pdf_path: str,
    ocr_dpi: int = settings.OCR_DPI,
    attempt_ocr: bool = settings.ENABLE_OCR,
    min_length: int = settings.MIN_TEXT_LENGTH,
) -> List[str]:
    """
    Extract and normalize text from PDF file page by page.
    
    Args:
        pdf_path: Path to the PDF file
        ocr_dpi: DPI setting when performing OCR on image-based pages
        
    Returns:
        List of normalized page texts
        
    Raises:
        Exception: If text extraction fails
    """
    pages = []
    try:
        logger.debug(f"Opening PDF file: {pdf_path}")
        doc = fitz.open(pdf_path)
        page_count = len(doc)
        logger.debug(f"Found {page_count} pages in PDF")
        
        for i, page in enumerate(doc):
            text = extract_page_text(
                page,
                ocr_dpi=ocr_dpi,
                attempt_ocr=attempt_ocr,
                min_length=min_length,
            )
            logger.debug(f"Extracted {len(text)} characters from page {i+1}")
            
            if not text.strip():
                logger.warning(f"Page {i+1} appears to be empty or unreadable")
                # Include empty page to maintain page numbering
                pages.append("")
                continue
                
            normalized_text = normalize_medical_text(text)
            if normalized_text.strip():
                pages.append(normalized_text)
                logger.debug(f"Page {i+1} normalized to {len(normalized_text)} characters")
            else:
                logger.warning(f"Page {i+1} was empty after normalization")
                pages.append("")  # Include empty page to maintain page numbering
        
        doc.close()
        logger.debug(f"Successfully processed {len(pages)} pages")
        return pages
        
    except Exception as e:
        logger.error(f"Failed to extract pages from {pdf_path}: {e}", exc_info=True)
        raise


def extract_pages_with_images(
    pdf_path: str,
    ocr_dpi: int = settings.OCR_DPI,
    attempt_ocr: bool = settings.ENABLE_OCR,
    min_length: int = settings.MIN_TEXT_LENGTH,
) -> List[Dict]:
    """
    Extract text and image data from a PDF file.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        List of dictionaries with page data including text and images
        
    Raises:
        Exception: If extraction fails
    """
    pages_data = []
    try:
        doc = fitz.open(pdf_path)
        
        for i, page in enumerate(doc):
            # Extract text
            text = extract_page_text(
                page,
                ocr_dpi=ocr_dpi,
                attempt_ocr=attempt_ocr,
                min_length=min_length,
            )
            normalized_text = normalize_medical_text(text) if text.strip() else ""
            
            # Extract images as PNG data
            image_list = page.get_images(full=True)
            images = []
            
            for img_index, img_info in enumerate(image_list):
                try:
                    xref = img_info[0]
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]
                    
                    # Get position information
                    bbox = page.get_image_bbox(img_info)
                    
                    images.append({
                        "index": img_index,
                        "bytes": image_bytes,
                        "bbox": [bbox.x0, bbox.y0, bbox.x1, bbox.y1],
                        "size": len(image_bytes)
                    })
                except Exception as e:
                    logger.warning(f"Failed to extract image {img_index} on page {i+1}: {e}")
            
            # Add page data to result
            pages_data.append({
                "page_num": i + 1,
                "text": normalized_text,
                "text_snippet": normalized_text[:300].replace("\n", " ").strip() if normalized_text else "",
                "images": images
            })
                
        doc.close()
        return pages_data
        
    except Exception as e:
        logger.error(f"Failed to extract pages with images from {pdf_path}: {e}", exc_info=True)
        raise


def iter_pages(
    path: str,
    ocr_dpi: int = settings.OCR_DPI,
    attempt_ocr: bool = settings.ENABLE_OCR,
    min_length: int = settings.MIN_TEXT_LENGTH,
) -> Generator[str, None, None]:
    """
    Generator that yields the text of each page from the PDF.
    Useful for streaming ingestion of huge files.
    
    Args:
        path: Path to the PDF file
        
    Yields:
        Text of each page
    """
    with fitz.open(path) as doc:
        for page in doc:
            yield extract_page_text(
                page,
                ocr_dpi=ocr_dpi,
                attempt_ocr=attempt_ocr,
                min_length=min_length,
            )


def get_pdf_metadata(pdf_path: str) -> Dict:
    """
    Extract metadata from a PDF file.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        Dictionary with metadata
        
    Raises:
        Exception: If extraction fails
    """
    try:
        doc = fitz.open(pdf_path)
        metadata = doc.metadata
        
        # Add some additional metadata
        metadata.update({
            "page_count": len(doc),
            "file_size": os.path.getsize(pdf_path),
            "encrypted": doc.is_encrypted,
            "form_fields": len(doc.get_form_text_fields())
        })
        
        doc.close()
        return metadata
        
    except Exception as e:
        logger.error(f"Failed to extract metadata from {pdf_path}: {e}", exc_info=True)
        raise