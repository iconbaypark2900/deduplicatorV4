'use client';

import React, { useState } from 'react';
import UploadDropzone from '../core/UploadDropzone';
import { documentService } from '../../services/documentService';
import { getAbsoluteApiUrl } from '../../services/baseApi';
import { UploadResponse, PageMetadata, DuplicateMatch, UploadTaskResponse, DocumentAnalysis } from '../../types/document';
import { ReviewData } from '../../types/review';
import DirectImageDisplay from '../core/DirectImageDisplay';

interface Props {
  settings: {
    chunkType: string;
    similarityThreshold: number;
  };
  onComplete?: (data: ReviewData) => void;
}

/**
 * SingleDocument component for analyzing a single document for internal duplicates.
 */
export default function SingleDocument({ settings, onComplete }: Props) {
  const [results, setResults] = useState<UploadResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedDuplicate, setSelectedDuplicate] = useState<DuplicateMatch | null>(null);

  // Handle file upload and analysis
  const handleUpload = async (files: File | File[]) => {
    const file = Array.isArray(files) ? files[0] : files;
    setIsLoading(true);
    setError(null);

    try {
      const task: UploadTaskResponse = await documentService.uploadDocument(file);

      // Poll document status until processing is complete
      for (let i = 0; i < 30; i++) {
        await new Promise((r) => setTimeout(r, 2000));
        try {
          const status = await documentService.getDocumentStatus(task.doc_id, task.task_id);
          if (
            (status.status && !status.status.startsWith('processing')) ||
            status.task_state === 'SUCCESS'
          ) {
            break;
          }
        } catch {
          /* Ignore errors and retry */
        }
      }

      const analysis: DocumentAnalysis = await documentService.getAnalysis(task.doc_id);

      const baseResult: UploadResponse = {
        doc_id: analysis.doc_id,
        status: analysis.status,
        pages: analysis.pages.map((p) => ({
          page_num: p.index + 1,
          page_hash: p.hash,
          text_snippet: p.text_snippet
        })),
        duplicates: analysis.duplicates
      };

      const enhancedResult: UploadResponse = {
        ...baseResult,
        pages: baseResult.pages.map((page) => ({
          ...page,
          imageUrl: getAbsoluteApiUrl(`/page/${page.page_hash}/image`)
        }))
      };

      setResults(enhancedResult);

      if (onComplete && analysis.duplicates && analysis.duplicates.length > 0) {
        const flaggedPages = analysis.duplicates.map((dup) => {
          const page1 = enhancedResult.pages[dup.page1_idx];
          const page2 = enhancedResult.pages[dup.page2_idx];

          return {
            pageNumber: dup.page1_idx + 1,
            pageHash: page1.page_hash,
            similarity: dup.similarity,
            imageUrl: page1.imageUrl,
            matchedPage: {
              pageNumber: dup.page2_idx + 1,
              documentId: analysis.doc_id,
              filename: file.name,
              pageHash: page2.page_hash,
              imageUrl: page2.imageUrl
            }
          };
        });

        onComplete({
          documentId: analysis.doc_id,
          filename: file.name,
          workflowType: 'single',
          flaggedPages,
          status: 'pending',
          reviewHistory: [],
          duplicateConfidence: analysis.duplicates.length > 0 ? 0.8 : 0.2
        });
      }
    } catch (error) {
      console.error('Document analysis failed:', error);
      setError('Failed to analyze document. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  // Get color based on similarity score
  const getSimilarityColor = (similarity: number): string => {
    if (similarity > 0.9) return 'bg-error';
    if (similarity > 0.7) return 'bg-warning';
    return 'bg-success';
  };

  return (
    <div className="space-y-6">
      <div className="card-bordered">
        <h3 className="text-lg font-semibold mb-4 text-text-primary">Single Document Analysis</h3>
        <p className="text-text-secondary mb-4">
          Upload a single document to analyze for internal duplicate pages.
        </p>
        <UploadDropzone 
          onUpload={handleUpload} 
          mode="single"
          label="Upload a document to analyze"
          sublabel="PDF files only (max 50MB)"
        />
      </div>

      {isLoading && (
        <div className="flex justify-center items-center py-8">
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-accent-primary"></div>
          <span className="ml-3 text-text-secondary">Analyzing document...</span>
        </div>
      )}

      {error && (
        <div className="bg-error/10 border border-error text-error px-4 py-3 rounded">
          <p>{error}</p>
        </div>
      )}

      {results && (
        <div className="space-y-6">
          {/* Document Summary */}
          <div className="card-bordered">
            <h3 className="text-xl font-bold mb-4 text-text-primary">Document Summary</h3>
            
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
              <div className="card">
                <h4 className="text-lg font-semibold text-text-secondary">Pages</h4>
                <p className="text-2xl font-bold text-text-primary">{results.pages.length}</p>
              </div>
              
              <div className="card">
                <h4 className="text-lg font-semibold text-text-secondary">Duplicates</h4>
                <p className="text-2xl font-bold text-text-primary">{results.duplicates ? results.duplicates.length : 0}</p>
              </div>
              
              <div className="card">
                <h4 className="text-lg font-semibold text-text-secondary">Status</h4>
                <p className="text-2xl font-bold text-text-primary capitalize">{results.status}</p>
              </div>
            </div>
          </div>
          
          {/* Duplicate Pages */}
          {results.duplicates && results.duplicates.length > 0 && (
            <div className="card-bordered">
              <h3 className="text-xl font-bold mb-4 text-text-primary">Duplicate Pages</h3>
              
              <div className="space-y-4">
                {results.duplicates.map((dup, idx) => (
                  <div 
                    key={idx} 
                    className="card cursor-pointer hover:bg-accent-secondary/10 transition-colors"
                    onClick={() => setSelectedDuplicate(
                      selectedDuplicate === dup ? null : dup
                    )}
                  >
                    <div className="flex justify-between items-center">
                      <div>
                        <h4 className="font-medium text-text-primary">
                          Page {dup.page1_idx + 1} ↔️ Page {dup.page2_idx + 1}
                        </h4>
                        <p className="text-sm text-text-secondary">
                          Similarity: {(dup.similarity * 100).toFixed(1)}%
                        </p>
                      </div>
                      <div className="w-16 h-2 rounded-full overflow-hidden">
                        <div 
                          className={`h-full ${getSimilarityColor(dup.similarity)}`}
                          style={{ width: `${dup.similarity * 100}%` }}
                        ></div>
                      </div>
                    </div>
                    
                    {selectedDuplicate === dup && (
                      <div className="mt-4 grid grid-cols-2 gap-4">
                        <div className="card-bordered overflow-hidden">
                          <h5 className="text-sm font-medium p-2 bg-surface">Page {dup.page1_idx + 1}</h5>
                          <div className="border-t border-b border-accent-secondary/20">
                            <DirectImageDisplay
                              pageNumber={dup.page1_idx + 1}
                              alt={`Page ${dup.page1_idx + 1}`}
                              className="w-full h-auto"
                            />
                          </div>
                          <p className="text-xs text-text-secondary p-2">
                            {results.pages[dup.page1_idx]?.text_snippet || "No preview available"}
                          </p>
                        </div>
                        <div className="card-bordered overflow-hidden">
                          <h5 className="text-sm font-medium p-2 bg-surface">Page {dup.page2_idx + 1}</h5>
                          <div className="border-t border-b border-accent-secondary/20">
                            <DirectImageDisplay
                              pageNumber={dup.page2_idx + 1}
                              alt={`Page ${dup.page2_idx + 1}`}
                              className="w-full h-auto"
                            />
                          </div>
                          <p className="text-xs text-text-secondary p-2">
                            {results.pages[dup.page2_idx]?.text_snippet || "No preview available"}
                          </p>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
          
          {/* All Pages */}
          <div className="card-bordered">
            <h3 className="text-xl font-bold mb-4 text-text-primary">All Pages</h3>
            
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
              {results.pages.map((page, idx) => {
                // Check if this page is involved in any duplicate
                const isDuplicate = results.duplicates ? 
                  results.duplicates.some(d => d.page1_idx === idx || d.page2_idx === idx) : 
                  false;
                
                return (
                  <div key={idx} className={`card overflow-hidden ${
                    isDuplicate ? 'border-l-4 border-l-error' : ''
                  }`}>
                    <div className="flex justify-between items-center">
                      <h4 className="font-medium text-text-primary">Page {page.page_num}</h4>
                      {isDuplicate && (
                        <span className="text-xs bg-error text-white px-2 py-1 rounded-full">
                          Duplicate
                        </span>
                      )}
                    </div>
                    
                    <div className="border-t border-b border-accent-secondary/20 my-2">
                      <DirectImageDisplay
                        pageNumber={page.page_num}
                        alt={`Page ${page.page_num}`}
                        className="w-full h-auto"
                      />
                    </div>
                    
                    <div>
                      <p className="text-xs text-text-secondary max-h-20 overflow-hidden">
                        {page.text_snippet || "No preview available"}
                      </p>
                      <div className="mt-2 text-xs text-text-secondary opacity-60 truncate">
                        Hash: {page.page_hash.substring(0, 12)}...
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}