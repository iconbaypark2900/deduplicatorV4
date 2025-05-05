"""
Utilities for finding and visualizing differences between documents.
"""

import re
import difflib
from typing import List, Dict, Tuple, Optional, Any
import logging
from PIL import Image, ImageDraw

# Configure logging
logger = logging.getLogger(__name__)


def compute_text_diff(text1: str, text2: str) -> Dict[str, Any]:
    """
    Compute differences between two text strings.
    Uses difflib to create a diff and formats results.
    
    Args:
        text1: First text
        text2: Second text
        
    Returns:
        Dictionary with formatted diff information
    """
    # Normalize texts
    def normalize(text):
        text = text.replace("\r\n", "\n")
        text = re.sub(r"\s+", " ", text)
        return text
    
    text1_norm = normalize(text1)
    text2_norm = normalize(text2)
    
    # Calculate differences
    diff = difflib.ndiff(text1_norm.splitlines(), text2_norm.splitlines())
    
    # Parse diff output
    result = {
        "additions": [],
        "deletions": [],
        "changes": [],
        "common": 0,
        "diff_lines": []
    }
    
    for line in diff:
        if line.startswith("+ "):
            result["additions"].append(line[2:])
            result["diff_lines"].append({"type": "addition", "text": line[2:]})
        elif line.startswith("- "):
            result["deletions"].append(line[2:])
            result["diff_lines"].append({"type": "deletion", "text": line[2:]})
        elif line.startswith("? "):
            # Diff marker line - we can ignore
            continue
        else:
            result["common"] += 1
            result["diff_lines"].append({"type": "common", "text": line[2:]})
    
    # Calculate similarity metrics
    total_lines = len(text1_norm.splitlines()) + len(text2_norm.splitlines())
    if total_lines > 0:
        result["similarity"] = (2 * result["common"]) / total_lines
    else:
        result["similarity"] = 1.0 if text1_norm == text2_norm else 0.0
    
    # Calculate word-level similarity
    words1 = set(re.findall(r'\b\w+\b', text1_norm.lower()))
    words2 = set(re.findall(r'\b\w+\b', text2_norm.lower()))
    
    if words1 or words2:
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        result["word_similarity"] = len(intersection) / len(union)
    else:
        result["word_similarity"] = 1.0 if text1_norm == text2_norm else 0.0
    
    return result


def find_similar_sections(text1: str, text2: str, threshold: float = 0.8) -> List[Dict[str, Any]]:
    """
    Find similar text sections between two documents.
    
    Args:
        text1: First text
        text2: Second text
        threshold: Similarity threshold for matching sections
        
    Returns:
        List of dictionaries with similar section information
    """
    # Split into paragraphs
    paragraphs1 = [p.strip() for p in text1.split("\n\n") if p.strip()]
    paragraphs2 = [p.strip() for p in text2.split("\n\n") if p.strip()]
    
    similar_sections = []
    
    for i, p1 in enumerate(paragraphs1):
        for j, p2 in enumerate(paragraphs2):
            # Skip very short paragraphs
            if len(p1) < 50 or len(p2) < 50:
                continue
                
            # Compute similarity using difflib
            seq = difflib.SequenceMatcher(None, p1, p2)
            similarity = seq.ratio()
            
            if similarity >= threshold:
                similar_sections.append({
                    "doc1_para": i,
                    "doc2_para": j,
                    "doc1_text": p1[:100] + "..." if len(p1) > 100 else p1,
                    "doc2_text": p2[:100] + "..." if len(p2) > 100 else p2,
                    "similarity": similarity
                })
    
    return similar_sections


def compute_changed_bounding_boxes(words1: List[Dict], words2: List[Dict]) -> Dict[str, List[Dict]]:
    """
    Compute bounding boxes for words that differ between two documents.
    
    Args:
        words1: List of word dictionaries for first document
        words2: List of word dictionaries for second document
        
    Returns:
        Dictionary with bounding boxes for changes
    """
    # Extract just the words without formatting/position
    text1 = " ".join(word["text"] for word in words1)
    text2 = " ".join(word["text"] for word in words2)
    
    # Get diff
    matcher = difflib.SequenceMatcher(None, text1, text2)
    
    # Process operations
    result = {
        "additions": [],
        "deletions": []
    }
    
    position1 = 0
    position2 = 0
    
    for op, i1, i2, j1, j2 in matcher.get_opcodes():
        if op == "delete":
            # Find words in this range
            while position1 < len(words1) and position1 <= i2:
                word = words1[position1]
                if position1 >= i1:
                    result["deletions"].append({
                        "text": word["text"],
                        "bbox": word["bbox"]
                    })
                position1 += 1
                
        elif op == "insert":
            # Find words in this range
            while position2 < len(words2) and position2 <= j2:
                word = words2[position2]
                if position2 >= j1:
                    result["additions"].append({
                        "text": word["text"],
                        "bbox": word["bbox"]
                    })
                position2 += 1
                
        elif op == "replace":
            # Handle deleted words
            while position1 < len(words1) and position1 <= i2:
                word = words1[position1]
                if position1 >= i1:
                    result["deletions"].append({
                        "text": word["text"],
                        "bbox": word["bbox"]
                    })
                position1 += 1
                
            # Handle added words
            while position2 < len(words2) and position2 <= j2:
                word = words2[position2]
                if position2 >= j1:
                    result["additions"].append({
                        "text": word["text"],
                        "bbox": word["bbox"]
                    })
                position2 += 1
                
        else:  # "equal"
            position1 += (i2 - i1)
            position2 += (j2 - j1)
    
    return result


def highlight_differences(image1: Image.Image, image2: Image.Image, 
                         diff_boxes: Dict[str, List[Dict]]) -> Tuple[Image.Image, Image.Image]:
    """
    Highlight differences between two document images.
    
    Args:
        image1: First image
        image2: Second image
        diff_boxes: Dictionary with bounding boxes for changes
        
    Returns:
        Tuple of (highlighted_image1, highlighted_image2)
    """
    # Create copies of images to draw on
    highlighted1 = image1.copy().convert("RGBA")
    highlighted2 = image2.copy().convert("RGBA")
    
    # Create draw objects
    draw1 = ImageDraw.Draw(highlighted1)
    draw2 = ImageDraw.Draw(highlighted2)
    
    # Highlight deletions in image1
    for word in diff_boxes["deletions"]:
        bbox = word["bbox"]
        draw1.rectangle(
            [bbox[0], bbox[1], bbox[0] + bbox[2], bbox[1] + bbox[3]],
            outline=(255, 0, 0, 255),  # Red outline
            fill=(255, 0, 0, 64),      # Transparent red fill
            width=2
        )
    
    # Highlight additions in image2
    for word in diff_boxes["additions"]:
        bbox = word["bbox"]
        draw2.rectangle(
            [bbox[0], bbox[1], bbox[0] + bbox[2], bbox[1] + bbox[3]],
            outline=(0, 255, 0, 255),  # Green outline
            fill=(0, 255, 0, 64),      # Transparent green fill
            width=2
        )
    
    return highlighted1, highlighted2


def create_diff_visualization(text1: str, text2: str) -> str:
    """
    Create an HTML visualization of the diff between two texts.
    
    Args:
        text1: First text
        text2: Second text
        
    Returns:
        HTML string with formatted diff
    """
    # Compute diff 
    diff_result = compute_text_diff(text1, text2)
    
    # Create HTML output
    html = [
        "<html><head>",
        "<style>",
        ".diff-container { font-family: monospace; white-space: pre-wrap; margin: 10px; }",
        ".diff-line { margin: 2px 0; padding: 2px 5px; border-radius: 3px; }",
        ".diff-common { background-color: #f8f8f8; }",
        ".diff-deletion { background-color: #ffecec; color: #b30000; text-decoration: line-through; }",
        ".diff-addition { background-color: #eaffea; color: #006700; }",
        ".diff-stats { margin: 10px; padding: 10px; background-color: #f0f0f0; border-radius: 5px; }",
        ".diff-stats-item { margin: 5px 0; }",
        "</style>",
        "</head><body>",
        "<div class='diff-stats'>",
        f"<div class='diff-stats-item'>Similarity: {diff_result['similarity']:.2%}</div>",
        f"<div class='diff-stats-item'>Word Similarity: {diff_result['word_similarity']:.2%}</div>",
        f"<div class='diff-stats-item'>Additions: {len(diff_result['additions'])}</div>",
        f"<div class='diff-stats-item'>Deletions: {len(diff_result['deletions'])}</div>",
        f"<div class='diff-stats-item'>Common: {diff_result['common']}</div>",
        "</div>",
        "<div class='diff-container'>"
    ]
    
    for line in diff_result["diff_lines"]:
        line_type = line["type"]
        text = line["text"].replace("<", "&lt;").replace(">", "&gt;")
        
        if line_type == "common":
            html.append(f"<div class='diff-line diff-common'>{text}</div>")
        elif line_type == "deletion":
            html.append(f"<div class='diff-line diff-deletion'>{text}</div>")
        elif line_type == "addition":
            html.append(f"<div class='diff-line diff-addition'>{text}</div>")
    
    html.append("</div></body></html>")
    
    return "\n".join(html)