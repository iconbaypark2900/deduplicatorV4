"""
Data science API endpoints.
Provides routes for medical content analysis, document clustering, and topic modeling.
"""

import os
import uuid
import json
import logging
from fastapi import APIRouter, UploadFile, File, HTTPException, Form, Body
from fastapi.responses import FileResponse, JSONResponse
from typing import List, Dict, Optional, Any
import tempfile

from backend.services.extractor import extract_text_and_pages, analyze_document_content
from ingestion.preprocessing import measure_medical_confidence, extract_medical_terms
from utils.config import settings

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/data-science", tags=["Data Science"])


@router.post("/medical")
async def analyze_medical_content(file: UploadFile = File(...)):
    """
    Analyze a document for medical content.
    
    Args:
        file: PDF file to analyze
        
    Returns:
        Medical content analysis results
        
    Raises:
        HTTPException: If analysis fails
    """
    try:
        # Save uploaded file temporarily
        temp_path = f"storage/tmp/{uuid.uuid4()}_{file.filename}"
        os.makedirs(os.path.dirname(temp_path), exist_ok=True)
        
        with open(temp_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # Extract document content
        full_text, pages_data = extract_text_and_pages(temp_path)
        
        # Check if text extraction was successful
        if not full_text:
            raise HTTPException(status_code=400, detail="Could not extract text from document")
        
        # Analyze document
        doc_analysis = analyze_document_content(temp_path)
        
        # Analyze pages for medical content
        pages_analysis = []
        medical_pages = 0
        
        for i, page in enumerate(pages_data):
            page_text = page.get("text", "")
            medical_confidence = page.get("medical_confidence", 0.0)
            medical_terms = page.get("medical_terms", [])
            
            # Determine if page is medical
            is_medical = medical_confidence > 0.6
            if is_medical:
                medical_pages += 1
            
            # Add page analysis
            pages_analysis.append({
                "page_num": i + 1,
                "is_medical": is_medical,
                "confidence": medical_confidence,
                "specialty": detect_specialty(page_text, medical_terms) if is_medical else None,
                "term_ratio": len(medical_terms) / len(page_text.split()) if page_text else 0,
                "terms": medical_terms[:20] if len(medical_terms) > 0 else None
            })
        
        # Determine the overall specialty
        overall_specialty = determine_document_specialty(pages_analysis)
        
        # Calculate medical page ratio
        medical_page_ratio = medical_pages / len(pages_data) if pages_data else 0
        
        # Create response
        result = {
            "document_id": str(uuid.uuid4()),
            "filename": file.filename,
            "is_medical": doc_analysis.get("is_medical", False),
            "confidence": doc_analysis.get("medical_confidence", 0.0),
            "specialty": overall_specialty,
            "medical_page_ratio": medical_page_ratio,
            "pages": pages_analysis
        }
        
        # Clean up
        try:
            os.unlink(temp_path)
        except:
            pass
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Medical analysis failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Medical analysis failed: {str(e)}")


@router.post("/cluster")
async def cluster_documents(files: List[UploadFile] = File(...)):
    """
    Cluster multiple documents based on similarity.
    
    Args:
        files: List of PDF files to analyze
        
    Returns:
        Clustering results with visualization data
        
    Raises:
        HTTPException: If clustering fails
    """
    try:
        # Check if files were uploaded
        if not files:
            raise HTTPException(status_code=400, detail="No files uploaded")
        
        # Save uploaded files temporarily
        temp_paths = []
        doc_ids = []
        
        for file in files:
            temp_path = f"storage/tmp/{uuid.uuid4()}_{file.filename}"
            os.makedirs(os.path.dirname(temp_path), exist_ok=True)
            
            with open(temp_path, "wb") as f:
                content = await file.read()
                f.write(content)
                
            temp_paths.append(temp_path)
            doc_ids.append(str(uuid.uuid4()))
        
        # Process documents
        nodes = []
        embeddings = []
        
        from similarity.embedding import embed_text
        
        for i, temp_path in enumerate(temp_paths):
            # Extract document content
            full_text, _ = extract_text_and_pages(temp_path)
            
            # Get embedding
            embedding = embed_text(full_text)
            embeddings.append(embedding)
            
            # Create node
            nodes.append({
                "doc_id": doc_ids[i],
                "filename": os.path.basename(temp_path).split("_", 1)[1],
                "x": 0,  # Will be updated after clustering
                "y": 0,  # Will be updated after clustering
                "cluster_id": None,  # Will be updated after clustering
                "connections": 0  # Will be updated after calculating edges
            })
        
        # Calculate similarities and create edges
        edges = []
        from similarity.search import compute_similarity
        
        for i in range(len(embeddings)):
            for j in range(i+1, len(embeddings)):
                similarity = compute_similarity(embeddings[i], embeddings[j])
                
                # Only keep edges with sufficient similarity
                if similarity > 0.5:
                    edges.append({
                        "source": doc_ids[i],
                        "target": doc_ids[j],
                        "weight": similarity
                    })
                    
                    # Update connection count
                    nodes[i]["connections"] += 1
                    nodes[j]["connections"] += 1
        
        # Perform clustering
        clusters = perform_clustering(embeddings, doc_ids)
        
        # Assign clusters to nodes
        for node in nodes:
            for cluster in clusters:
                if node["doc_id"] in cluster["documents"]:
                    node["cluster_id"] = cluster["cluster_id"]
                    break
        
        # Calculate node positions using a simple force-directed layout
        calculate_node_positions(nodes, edges, clusters)
        
        # Calculate largest cluster size
        largest_cluster_size = max(len(cluster["documents"]) for cluster in clusters) if clusters else 0
        
        # Create response
        result = {
            "nodes": nodes,
            "edges": edges,
            "clusters": clusters,
            "total_documents": len(nodes),
            "total_clusters": len(clusters),
            "largest_cluster_size": largest_cluster_size
        }
        
        # Clean up
        for temp_path in temp_paths:
            try:
                os.unlink(temp_path)
            except:
                pass
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document clustering failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Document clustering failed: {str(e)}")


@router.post("/content")
async def analyze_content(files: List[UploadFile] = File(...)):
    """
    Analyze document content for topics, entities, and structure.
    
    Args:
        files: List of PDF files to analyze
        
    Returns:
        Content analysis results
        
    Raises:
        HTTPException: If analysis fails
    """
    try:
        # Check if files were uploaded
        if not files:
            raise HTTPException(status_code=400, detail="No files uploaded")
        
        # Save uploaded files temporarily
        temp_paths = []
        
        for file in files:
            temp_path = f"storage/tmp/{uuid.uuid4()}_{file.filename}"
            os.makedirs(os.path.dirname(temp_path), exist_ok=True)
            
            with open(temp_path, "wb") as f:
                content = await file.read()
                f.write(content)
                
            temp_paths.append(temp_path)
        
        # Process documents
        all_texts = []
        all_terms = []
        section_counts = {}
        avg_word_count = 0
        
        for temp_path in temp_paths:
            # Extract document content
            full_text, pages_data = extract_text_and_pages(temp_path)
            
            # Skip if text extraction failed
            if not full_text:
                continue
                
            all_texts.append(full_text)
            
            # Count words
            word_count = len(full_text.split())
            avg_word_count += word_count
            
            # Extract medical terms
            terms = extract_medical_terms(full_text)
            all_terms.extend(terms)
            
            # Detect sections
            from ingestion.preprocessing import detect_section_headers
            sections = detect_section_headers(full_text)
            
            for section in sections:
                section_name = section["section"].lower()
                if section_name in section_counts:
                    section_counts[section_name] += 1
                else:
                    section_counts[section_name] = 1
        
        # Calculate average word count
        avg_word_count = avg_word_count / len(all_texts) if all_texts else 0
        
        # Extract topics using a simple TF-IDF approach
        topics = []
        if all_texts:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.decomposition import NMF
            
            # Number of topics to extract
            n_topics = min(5, len(all_texts))
            
            if n_topics > 1:
                # Create TF-IDF representation
                vectorizer = TfidfVectorizer(max_features=1000, stop_words='english')
                tfidf = vectorizer.fit_transform(all_texts)
                
                # Extract topics
                nmf = NMF(n_components=n_topics, random_state=42)
                nmf.fit(tfidf)
                
                # Get feature names
                feature_names = vectorizer.get_feature_names_out()
                
                # Create topics
                for topic_idx, topic in enumerate(nmf.components_):
                    top_words = [feature_names[i] for i in topic.argsort()[:-11:-1]]
                    topics.append({
                        "topic_id": topic_idx,
                        "words": top_words,
                        "weight": float(topic.sum() / topic.size)
                    })
        
        # Process medical terms
        term_counts = {}
        medication_counts = {}
        condition_counts = {}
        procedure_counts = {}
        
        for term in all_terms:
            term_lower = term.lower()
            
            # Count general medical terms
            if term_lower in term_counts:
                term_counts[term_lower] += 1
            else:
                term_counts[term_lower] = 1
            
            # Attempt to categorize term
            if term_lower.endswith(('mg', 'mcg', 'ml', 'g')):
                # Likely a medication
                if term_lower in medication_counts:
                    medication_counts[term_lower] += 1
                else:
                    medication_counts[term_lower] = 1
            elif any(suffix in term_lower for suffix in ('itis', 'osis', 'emia')):
                # Likely a condition
                if term_lower in condition_counts:
                    condition_counts[term_lower] += 1
                else:
                    condition_counts[term_lower] = 1
            elif any(suffix in term_lower for suffix in ('ectomy', 'otomy', 'plasty', 'scopy')):
                # Likely a procedure
                if term_lower in procedure_counts:
                    procedure_counts[term_lower] += 1
                else:
                    procedure_counts[term_lower] = 1
        
        # Format section data
        sections_data = []
        for section_name, count in section_counts.items():
            sections_data.append({
                "name": section_name,
                "count": count
            })
        
        # Sort sections by frequency
        sections_data.sort(key=lambda x: x["count"], reverse=True)
        
        # Format term data
        def format_term_counts(counts_dict):
            return [{"term": term, "count": count} for term, count in sorted(counts_dict.items(), key=lambda x: x[1], reverse=True)]
        
        medical_terms = format_term_counts(term_counts)
        medications = format_term_counts(medication_counts)
        conditions = format_term_counts(condition_counts)
        procedures = format_term_counts(procedure_counts)
        
        # Create response
        result = {
            "document_id": str(uuid.uuid4()),
            "filename": files[0].filename if len(files) == 1 else None,
            "total_documents": len(all_texts),
            "topics": topics,
            "sections": sections_data,
            "medical_terms": medical_terms[:50],
            "medications": medications[:30],
            "conditions": conditions[:30],
            "procedures": procedures[:30],
            "average_document_length": avg_word_count,
            "average_word_count": avg_word_count
        }
        
        # Clean up
        for temp_path in temp_paths:
            try:
                os.unlink(temp_path)
            except:
                pass
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Content analysis failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Content analysis failed: {str(e)}")


# Helper functions

def detect_specialty(text: str, medical_terms: List[str]) -> Optional[str]:
    """
    Attempt to detect medical specialty based on text and terms.
    This is a simple heuristic approach.
    
    Args:
        text: Page text
        medical_terms: List of medical terms
        
    Returns:
        Detected specialty or None
    """
    # Define specialty keywords
    specialties = {
        "cardiology": ["heart", "cardiac", "ecg", "ekg", "coronary", "arrhythmia", "myocardial"],
        "neurology": ["brain", "neural", "neuro", "seizure", "epilepsy", "cognitive"],
        "oncology": ["cancer", "tumor", "oncology", "malignant", "chemotherapy", "radiation"],
        "orthopedics": ["bone", "joint", "fracture", "orthopedic", "musculoskeletal"],
        "pediatrics": ["child", "pediatric", "infant", "adolescent"],
        "radiology": ["imaging", "ct scan", "mri", "xray", "x-ray", "radiograph"]
    }
    
    # Count specialty term occurrences
    specialty_counts = {specialty: 0 for specialty in specialties}
    
    # Check text
    text_lower = text.lower()
    for specialty, keywords in specialties.items():
        for keyword in keywords:
            if keyword in text_lower:
                specialty_counts[specialty] += 1
    
    # Check medical terms
    for term in medical_terms:
        term_lower = term.lower()
        for specialty, keywords in specialties.items():
            for keyword in keywords:
                if keyword in term_lower:
                    specialty_counts[specialty] += 1
    
    # Find specialty with highest count
    max_count = 0
    max_specialty = None
    
    for specialty, count in specialty_counts.items():
        if count > max_count:
            max_count = count
            max_specialty = specialty
    
    # Only return specialty if sufficient evidence
    return max_specialty if max_count >= 2 else None


def determine_document_specialty(pages_analysis: List[Dict[str, Any]]) -> Optional[str]:
    """
    Determine the overall document specialty based on page specialties.
    
    Args:
        pages_analysis: List of page analysis data
        
    Returns:
        Overall document specialty or None
    """
    # Count specialty occurrences
    specialty_counts = {}
    
    for page in pages_analysis:
        specialty = page.get("specialty")
        if specialty:
            if specialty in specialty_counts:
                specialty_counts[specialty] += 1
            else:
                specialty_counts[specialty] = 1
    
    # Find specialty with highest count
    max_count = 0
    max_specialty = None
    
    for specialty, count in specialty_counts.items():
        if count > max_count:
            max_count = count
            max_specialty = specialty
    
    return max_specialty


def perform_clustering(embeddings: List[List[float]], doc_ids: List[str]) -> List[Dict[str, Any]]:
    """
    Perform clustering on document embeddings.
    
    Args:
        embeddings: List of document embeddings
        doc_ids: List of document IDs
        
    Returns:
        List of cluster information
    """
    if len(embeddings) <= 1:
        # If only one document, return a single cluster
        if len(embeddings) == 1:
            return [{
                "cluster_id": "cluster_0",
                "documents": doc_ids,
                "center_x": 0,
                "center_y": 0
            }]
        else:
            return []
    
    try:
        # Convert embeddings to numpy array
        import numpy as np
        embeddings_array = np.array(embeddings)
        
        # Apply clustering algorithm
        from sklearn.cluster import KMeans
        
        # Determine number of clusters (k)
        k = min(5, len(embeddings))
        
        # Perform clustering
        kmeans = KMeans(n_clusters=k, random_state=42)
        cluster_labels = kmeans.fit_predict(embeddings_array)
        
        # Group documents by cluster
        clusters = []
        for i in range(k):
            cluster_docs = [doc_ids[j] for j in range(len(doc_ids)) if cluster_labels[j] == i]
            
            if cluster_docs:
                clusters.append({
                    "cluster_id": f"cluster_{i}",
                    "documents": cluster_docs,
                    "center_x": 0,  # Will be updated
                    "center_y": 0   # Will be updated
                })
        
        return clusters
        
    except Exception as e:
        logger.error(f"Clustering failed: {str(e)}")
        
        # Return a single cluster as fallback
        return [{
            "cluster_id": "cluster_0",
            "documents": doc_ids,
            "center_x": 0,
            "center_y": 0
        }]


def calculate_node_positions(nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]], clusters: List[Dict[str, Any]]):
    """
    Calculate positions for nodes in the visualization.
    Uses a simple force-directed layout algorithm.
    
    Args:
        nodes: List of node data (modified in-place)
        edges: List of edge data
        clusters: List of cluster data (modified in-place)
    """
    import math
    import random
    
    # Initialize random positions
    for node in nodes:
        node["x"] = random.uniform(-10, 10)
        node["y"] = random.uniform(-10, 10)
    
    # Simple force-directed layout simulation
    iterations = 50
    temperature = 10.0
    
    # Create node lookup
    node_lookup = {node["doc_id"]: node for node in nodes}
    
    for _ in range(iterations):
        # Calculate repulsive forces
        for i, node1 in enumerate(nodes):
            force_x = 0
            force_y = 0
            
            # Repulsion from other nodes
            for j, node2 in enumerate(nodes):
                if i != j:
                    dx = node1["x"] - node2["x"]
                    dy = node1["y"] - node2["y"]
                    distance = math.sqrt(dx*dx + dy*dy) + 0.1  # Avoid division by zero
                    
                    # Greater repulsion for nodes in different clusters
                    repulsion = 5.0
                    if node1["cluster_id"] != node2["cluster_id"]:
                        repulsion = 10.0
                    
                    force_x += repulsion * dx / (distance * distance)
                    force_y += repulsion * dy / (distance * distance)
            
            # Apply repulsive forces
            node1["x"] += force_x * temperature / 100
            node1["y"] += force_y * temperature / 100
        
        # Calculate attractive forces
        for edge in edges:
            source = node_lookup.get(edge["source"])
            target = node_lookup.get(edge["target"])
            
            if source and target:
                dx = source["x"] - target["x"]
                dy = source["y"] - target["y"]
                distance = math.sqrt(dx*dx + dy*dy) + 0.1  # Avoid division by zero
                
                # Attraction strength based on edge weight
                attraction = edge["weight"] * 2.0
                
                # Apply attractive forces
                source["x"] -= dx * attraction / 10
                source["y"] -= dy * attraction / 10
                target["x"] += dx * attraction / 10
                target["y"] += dy * attraction / 10
        
        # Cool down
        temperature *= 0.9
    
    # Calculate cluster centers
    for cluster in clusters:
        cluster_nodes = [node for node in nodes if node["cluster_id"] == cluster["cluster_id"]]
        
        if cluster_nodes:
            cluster["center_x"] = sum(node["x"] for node in cluster_nodes) / len(cluster_nodes)
            cluster["center_y"] = sum(node["y"] for node in cluster_nodes) / len(cluster_nodes)