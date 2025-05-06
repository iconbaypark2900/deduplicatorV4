"""
Image service for handling page image retrieval and mapping.
Provides functions to find and map page images by page number.
"""

import os
import logging
from typing import Dict, List, Optional, Tuple
from pathlib import Path

# Configure logging
logger = logging.getLogger(__name__)

# Constants
TMP_DIR = "storage/tmp"
PAGE_IMAGES_DIR = "storage/page_images"

class ImageMapper:
    """
    Class to handle image mapping and retrieval.
    Uses a cache to avoid repeatedly scanning the directory.
    """
    
    def __init__(self):
        self.page_image_map: Dict[int, List[str]] = {}
        self.last_refresh_time = 0
        self.refresh_interval = 5  # Refresh cache every 5 seconds
        
    def refresh_mapping(self) -> None:
        """
        Scan the tmp directory and build a mapping of page numbers to image files.
        """
        import time
        current_time = time.time()
        
        # Only refresh if enough time has passed
        if current_time - self.last_refresh_time < self.refresh_interval:
            return
            
        self.page_image_map = {}
        
        # Scan the tmp directory
        if os.path.exists(TMP_DIR):
            for filename in os.listdir(TMP_DIR):
                if filename.endswith(".png") and filename.startswith("page"):
                    try:
                        # Extract page number from filename (page{number}_{hash}.png)
                        parts = filename.split("_")
                        if len(parts) >= 2:
                            page_num_str = parts[0].replace("page", "")
                            page_num = int(page_num_str)
                            
                            # Add file to the mapping
                            if page_num not in self.page_image_map:
                                self.page_image_map[page_num] = []
                            
                            self.page_image_map[page_num].append(filename)
                    except (ValueError, IndexError) as e:
                        logger.warning(f"Failed to parse filename {filename}: {str(e)}")
        
        self.last_refresh_time = current_time
        logger.info(f"Refreshed image mapping: {len(self.page_image_map)} page numbers mapped")
        
    def get_image_path(self, page_number: int) -> Optional[str]:
        """
        Get the full file path for an image by page number.
        
        Args:
            page_number: The page number to find
            
        Returns:
            Full file path to the image, or None if not found
        """
        self.refresh_mapping()
        
        if page_number in self.page_image_map and self.page_image_map[page_number]:
            # Use the first image found for this page number
            filename = self.page_image_map[page_number][0]
            return os.path.join(TMP_DIR, filename)
        
        return None
        
    def get_image_url(self, page_number: int) -> Optional[str]:
        """
        Get the URL for an image by page number.
        
        Args:
            page_number: The page number to find
            
        Returns:
            URL to the image, or None if not found
        """
        self.refresh_mapping()
        
        if page_number in self.page_image_map and self.page_image_map[page_number]:
            # Use the first image found for this page number
            filename = self.page_image_map[page_number][0]
            return f"/temp/{filename}"
        
        return None
        
    def get_all_images_for_page(self, page_number: int) -> List[Tuple[str, str]]:
        """
        Get all images for a specific page number.
        
        Args:
            page_number: The page number to find
            
        Returns:
            List of tuples (filename, full path) for all images of the page
        """
        self.refresh_mapping()
        
        result = []
        if page_number in self.page_image_map:
            for filename in self.page_image_map[page_number]:
                full_path = os.path.join(TMP_DIR, filename)
                result.append((filename, full_path))
                
        return result
        
    def get_page_count(self) -> int:
        """
        Get the total number of unique page numbers found.
        
        Returns:
            Number of unique page numbers
        """
        self.refresh_mapping()
        return len(self.page_image_map)
        
    def get_highest_page_number(self) -> int:
        """
        Get the highest page number found.
        
        Returns:
            Highest page number, or 0 if no pages found
        """
        self.refresh_mapping()
        if not self.page_image_map:
            return 0
        return max(self.page_image_map.keys())


# Create a singleton instance for global use
image_mapper = ImageMapper()


def get_page_image_path(page_number: int) -> Optional[str]:
    """
    Get the file path for a page image.
    
    Args:
        page_number: The page number
        
    Returns:
        File path to the image, or None if not found
    """
    return image_mapper.get_image_path(page_number)


def get_page_image_url(page_number: int) -> Optional[str]:
    """
    Get the URL for a page image.
    
    Args:
        page_number: The page number
        
    Returns:
        URL to the image, or None if not found
    """
    return image_mapper.get_image_url(page_number)


def get_all_page_images() -> Dict[int, List[str]]:
    """
    Get a mapping of all page numbers to their image files.
    
    Returns:
        Dictionary mapping page numbers to lists of image filenames
    """
    image_mapper.refresh_mapping()
    return image_mapper.page_image_map 