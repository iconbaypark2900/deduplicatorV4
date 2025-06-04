import { api } from './baseApi';
import {
  DocumentAnalysis,
  PageMetadata,
  UploadResponse,
  UploadTaskResponse,
  ReviewRequest,
  PageMetadataResponse,
  BatchFolderResponse,
  SelectedPage
} from '../types/document';

/**
 * Service for core document operations.
 * Handles document upload, analysis, and review functions.
 */
export const documentService = {
  /**
   * Upload a single document for analysis
   */
  async uploadDocument(file: File): Promise<UploadTaskResponse> {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await api.post('/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });

    return response.data;
  },
  
  /**
   * Get detailed analysis for a document
   */
  async getAnalysis(documentId: string): Promise<DocumentAnalysis> {
    const response = await api.get(`/documents/${documentId}/analysis`);
    return response.data;
  },
  
  /**
   * Get metadata for a specific page by hash
   */
  async getPageMetadata(hash: string): Promise<PageMetadataResponse> {
    const response = await api.get(`/page/${hash}`);
    return response.data;
  },
  
  /**
   * Get page image as blob
   */
  async getPageImage(hash: string): Promise<Blob> {
    const response = await api.get(`/page/${hash}/image`, { 
      responseType: 'blob' 
    });
    return response.data;
  },
  
  /**
   * Submit a review decision for a document
   */
  async submitReview(review: ReviewRequest): Promise<void> {
    await api.post('/review', review);
  },
  
  /**
   * Analyze a batch of documents for duplicates
   */
  async analyzeBatchFolder(files: File[], settings: { 
    chunkType: string; 
    similarityThreshold: number 
  }): Promise<BatchFolderResponse> {
    const formData = new FormData();
    
    files.forEach((file) => {
      if (file.type === 'application/pdf') {
        formData.append('files', file);
      }
    });
    
    formData.append('chunk_type', settings.chunkType);
    formData.append('similarity_threshold', settings.similarityThreshold.toString());
    
    const response = await api.post('/upload/batch-folder', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
    
    return response.data;
  },
  
  /**
   * Compare two documents for similarities
   */
  async compareDocuments(file1: File, file2: File): Promise<any> {
    const formData = new FormData();
    formData.append('file1', file1);
    formData.append('file2', file2);
    
    const response = await api.post('/compare', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
    
    return response.data;
  },
  
  /**
   * Analyze a single document for internal page similarities
   */
  async analyzeIntraDocument(file: File, threshold: number): Promise<any> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('threshold', threshold.toString());
    
    const response = await api.post('/analyze/intra-document', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 300000 // 5 minutes timeout for large documents
    });
    
    return response.data;
  },

  /**
   * Analyze stored document pages by doc_id
   */
  async analyzeStoredDocument(docId: string, threshold: number): Promise<any> {
    const response = await api.get(`/documents/${docId}/analyze-internal-pages`, {
      params: { threshold }
    });
    return response.data;
  },
  
  /**
   * Rebuild a document using selected pages
   */
  async rebuildDocument(documentId: string, selectedPages: SelectedPage[]): Promise<Blob> {
    const response = await api.post('/documents/rebuild', {
      doc_id: documentId,
      selected_pages: selectedPages
    }, { 
      responseType: 'blob' 
    });
    
    return response.data;
  },
  
  /**
   * Update the status of a document (keep/archive)
   */
  async updateDocumentStatus(documentId: string, status: string, notes?: string): Promise<void> {
    await api.post(`/documents/${documentId}/status`, {
      status,
      notes
    });
  }
};

/**
 * Helper function for single document upload
 */
export async function uploadSingle(file: File) {
  const form = new FormData();
  form.append("file", file);
  
  const { data } = await api.post("/upload/single", form, {
    headers: { "Content-Type": "multipart/form-data" }
  });
  
  return data;
}

/**
 * Helper function for batch document upload
 */
export async function uploadBatch(files: File[]) {
  const form = new FormData();
  files.forEach((f) => form.append("files", f));
  
  const { data } = await api.post("/upload/batch", form, {
    headers: { "Content-Type": "multipart/form-data" }
  });
  
  return data;
}

/**
 * Helper function for document pair comparison
 */
export async function comparePair(fileA: File, fileB: File) {
  const form = new FormData();
  form.append("file1", fileA);
  form.append("file2", fileB);
  
  const { data } = await api.post("/compare", form, {
    headers: { "Content-Type": "multipart/form-data" }
  });
  
  return data;
}