import { api } from './baseApi';
import {
  MedicalAnalysisResult,
  ClusteringResult,
  ContentAnalysisResult
} from '../types/document';

/**
 * Service for data science operations.
 * Handles medical analysis, clustering, and content analysis functions.
 * These endpoints map to the data_science module in the backend.
 */
export const dataScienceService = {
  /**
   * Analyze document for medical content
   */
  async analyzeMedicalContent(file: File): Promise<MedicalAnalysisResult> {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await api.post('/data-science/medical', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
    
    return response.data;
  },
  
  /**
   * Analyze multiple documents to identify medical content 
   * in a batch operation
   */
  async analyzeMedicalBatch(files: File[]): Promise<MedicalAnalysisResult[]> {
    const formData = new FormData();
    
    files.forEach(file => {
      if (file.type === 'application/pdf') {
        formData.append('files', file);
      }
    });
    
    const response = await api.post('/data-science/medical/batch', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
    
    return response.data;
  },
  
  /**
   * Cluster documents based on similarity
   */
  async clusterDocuments(files: File[]): Promise<ClusteringResult> {
    const formData = new FormData();
    
    files.forEach(file => {
      if (file.type === 'application/pdf') {
        formData.append('files', file);
      }
    });
    
    const response = await api.post('/data-science/cluster', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
    
    return response.data;
  },
  
  /**
   * Get cluster visualization as an image
   */
  async getClusterVisualization(clusterId: string): Promise<Blob> {
    const response = await api.get(`/data-science/cluster/${clusterId}/visualization`, {
      responseType: 'blob'
    });
    
    return response.data;
  },
  
  /**
   * Analyze document content for topics, entities, and sections
   */
  async analyzeContent(files: File[]): Promise<ContentAnalysisResult> {
    const formData = new FormData();
    
    files.forEach(file => {
      if (file.type === 'application/pdf') {
        formData.append('files', file);
      }
    });
    
    const response = await api.post('/data-science/content', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
    
    return response.data;
  },
  
  /**
   * Get detailed content analysis report as HTML
   */
  async getContentReport(reportId: string): Promise<Blob> {
    const response = await api.get(`/data-science/content/${reportId}/report`, {
      responseType: 'blob'
    });
    
    return response.data;
  },
  
  /**
   * Train medical classifier with a dataset
   */
  async trainMedicalClassifier(dataset: File): Promise<{ accuracy: number }> {
    const formData = new FormData();
    formData.append('dataset', dataset);
    
    const response = await api.post('/data-science/train', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
    
    return response.data;
  }
};