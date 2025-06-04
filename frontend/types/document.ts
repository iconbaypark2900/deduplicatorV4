/**
 * Type definitions for all document-related data.
 * These types are aligned with the backend response structures.
 */

// Core document types
export interface PageInfo {
    index: number;
    hash: string;
    text_snippet: string;
    text?: string;
    medical_confidence?: number;
    duplicate_confidence?: number;
  }
  
  export interface DuplicateMatch {
    page1_idx: number;
    page2_idx: number;
    similarity: number;
    type?: 'exact' | 'near';
  }
  
  export interface DocumentAnalysis {
    doc_id: string;
    filename: string;
    pages: PageInfo[];
    duplicates: DuplicateMatch[];
    status: string;
    lastReviewer?: string;
    lastReviewedAt?: string;
    reviewHistory?: ReviewHistoryEntry[];
  }
  
  export interface PageHashInfo {
    hash: string;
    filename: string;
    doc_id: string;
    page_number: number;
  }
  
  export interface SelectedPage {
    source_doc_id: string;
    source_dir: 'unique' | 'deduplicated';
    page_number: number;
  }
  
  export interface PageMetadata {
    page_num: number;
    page_hash: string;
    text_snippet: string;
    decision?: string;
    reviewed_by?: string;
    reviewed_at?: string;
    filename?: string;
    doc_id?: string;
    imageUrl?: string;
  }
  
  export interface MatchDetails {
    matched_doc: string;
    similarity: number;
  }
  
  export interface UploadResponse {
    doc_id: string;
    status: string;
    match?: MatchDetails | null;
    pages: PageMetadata[];
    duplicates?: DuplicateMatch[];
  }

  export interface UploadTaskResponse {
    doc_id: string;
    task_id: string;
  }

  export interface DocumentStatus {
    doc_id: string;
    status?: string | null;
    task_state?: string | null;
    message?: string | null;
  }
  
  export interface ReviewRequest {
    doc_id: string;
    pages: string[];
    decision: string;
    reviewer: string;
    notes?: string;
  }
  
  export interface PageMetadataResponse {
    page_hash: string;
    page_num: number;
    filename: string;
    doc_id: string;
    pdf_path?: string;
  }
  
  export type ReviewStatus = 'pending' | 'keep' | 'archive';
  
  export interface ReviewHistoryEntry {
    reviewer: string;
    status: ReviewStatus;
    timestamp: string;
    notes?: string;
  }
  
  export interface BatchFolderResult {
    type: 'exact_duplicate' | 'near_duplicate';
    file1: string;
    file2: string;
    similarity?: number;
  }
  
  export interface BatchFolderResponse {
    total_documents: number;
    duplicates_found: number;
    results: BatchFolderResult[];
  }
  
  // Data Science types
  
  export interface MedicalPageAnalysis {
    page_num: number;
    is_medical: boolean;
    confidence: number;
    specialty?: string;
    term_ratio: number;
    terms?: string[];
  }
  
  export interface MedicalAnalysisResult {
    document_id: string;
    filename: string;
    is_medical: boolean;
    confidence: number;
    specialty?: string;
    medical_page_ratio: number;
    pages: MedicalPageAnalysis[];
  }
  
  export interface ClusterNode {
    doc_id: string;
    filename: string;
    x: number;
    y: number;
    cluster_id?: string;
    connections: number;
  }
  
  export interface ClusterEdge {
    source: string; // doc_id
    target: string; // doc_id
    weight: number;
  }
  
  export interface Cluster {
    cluster_id: string;
    documents: string[]; // List of doc_ids
    center_x: number;
    center_y: number;
  }
  
  export interface ClusteringResult {
    nodes: ClusterNode[];
    edges: ClusterEdge[];
    clusters: Cluster[];
    visualization_url?: string;
    total_documents: number;
    total_clusters: number;
    largest_cluster_size: number;
  }
  
  export interface TopicModel {
    topic_id: number;
    words: string[];
    weight: number;
  }
  
  export interface MedicalEntityCount {
    term: string;
    count: number;
  }
  
  export interface SectionData {
    name: string;
    count: number;
  }
  
  export interface ContentAnalysisResult {
    document_id?: string;
    filename?: string;
    total_documents: number;
    topics: TopicModel[];
    sections: SectionData[];
    medical_terms: MedicalEntityCount[];
    medications: MedicalEntityCount[];
    conditions: MedicalEntityCount[];
    procedures: MedicalEntityCount[];
    average_document_length: number;
    average_word_count: number;
    report_url?: string;
  }