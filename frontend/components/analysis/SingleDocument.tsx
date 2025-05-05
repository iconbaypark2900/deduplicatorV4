'use client';

import React, { useState } from 'react';
import UploadDropzone from '../core/UploadDropzone';
import { documentService } from '../../services/documentService';
import { getAbsoluteApiUrl } from '../../services/baseApi';
import { UploadResponse, PageMetadata, DuplicateMatch } from '../../types/document';
import { ReviewData } from '../../types/review';

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
      // First get basic document data
      const result = await documentService.uploadDocument(file);
      
      // Add direct image URLs to each page using the same endpoint that works in the Review modal
      // This mirrors how DocumentComparison processes image URLs
      const enhancedResult: UploadResponse = {
        ...result,
        pages: result.pages.map(page => ({
          ...page,
          imageUrl: getAbsoluteApiUrl(`/page/${page.page_hash}/image`)
        }))
      };
      
      setResults(enhancedResult);
      
      // If onComplete callback is provided, format data for review
      if (onComplete && result.duplicates && result.duplicates.length > 0) {
        const flaggedPages = result.duplicates.map(dup => {
          // Store the image URLs directly in the flagged pages
          // This is similar to how DocumentComparison attaches image URLs
          const page1 = result.pages[dup.page1_idx];
          const page2 = result.pages[dup.page2_idx];
          
          return {
            pageNumber: dup.page1_idx + 1,
            pageHash: page1.page_hash,
            similarity: dup.similarity,
            imageUrl: getAbsoluteApiUrl(`/page/${page1.page_hash}/image`),
            matchedPage: {
              pageNumber: dup.page2_idx + 1,
              documentId: result.doc_id,
              filename: file.name,
              pageHash: page2.page_hash,
              imageUrl: getAbsoluteApiUrl(`/page/${page2.page_hash}/image`)
            }
          };
        });
        
        onComplete({
          documentId: result.doc_id,
          filename: file.name,
          workflowType: 'single',
          flaggedPages,
          status: 'pending',
          reviewHistory: [],
          duplicateConfidence: result.duplicates.length > 0 ? 0.8 : 0.2
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
    if (similarity > 0.9) return 'bg-red-500 dark:bg-red-600';
    if (similarity > 0.7) return 'bg-yellow-500 dark:bg-yellow-600';
    return 'bg-green-500 dark:bg-green-600';
  };

  return (
    <div className="space-y-6">
      <div className="bg-black text-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold mb-4">Single Document Analysis</h3>
        <p className="text-gray-300 mb-4">
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
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
          <span className="ml-3 text-gray-600 dark:text-gray-400">Analyzing document...</span>
        </div>
      )}

      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded dark:bg-red-900/30 dark:text-red-300 dark:border-red-800">
          <p>{error}</p>
        </div>
      )}

      {results && (
        <div className="space-y-6">
          {/* Document Summary */}
          <div className="bg-black text-white rounded-lg shadow p-6">
            <h3 className="text-xl font-bold mb-4">Document Summary</h3>
            
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
              <div className="border border-gray-700 rounded-lg p-4 bg-gray-900">
                <h4 className="text-lg font-semibold text-gray-300">Pages</h4>
                <p className="text-2xl font-bold">{results.pages.length}</p>
              </div>
              
              <div className="border border-gray-700 rounded-lg p-4 bg-gray-900">
                <h4 className="text-lg font-semibold text-gray-300">Duplicates</h4>
                <p className="text-2xl font-bold">{results.duplicates ? results.duplicates.length : 0}</p>
              </div>
              
              <div className="border border-gray-700 rounded-lg p-4 bg-gray-900">
                <h4 className="text-lg font-semibold text-gray-300">Status</h4>
                <p className="text-2xl font-bold capitalize">{results.status}</p>
              </div>
            </div>
          </div>
          
          {/* Duplicate Pages */}
          {results.duplicates && results.duplicates.length > 0 && (
            <div className="bg-black text-white rounded-lg shadow p-6">
              <h3 className="text-xl font-bold mb-4">Duplicate Pages</h3>
              
              <div className="space-y-4">
                {results.duplicates.map((dup, idx) => (
                  <div 
                    key={idx} 
                    className="border border-gray-700 rounded-lg p-4 bg-gray-900 cursor-pointer hover:bg-gray-800 transition-colors"
                    onClick={() => setSelectedDuplicate(
                      selectedDuplicate === dup ? null : dup
                    )}
                  >
                    <div className="flex justify-between items-center">
                      <div>
                        <h4 className="font-medium">
                          Page {dup.page1_idx + 1} ↔️ Page {dup.page2_idx + 1}
                        </h4>
                        <p className="text-sm text-gray-400">
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
                        <div className="border border-gray-700 rounded-lg overflow-hidden">
                          <h5 className="text-sm font-medium p-2 bg-gray-800">Page {dup.page1_idx + 1}</h5>
                          <div className="border-t border-b border-gray-700">
                            <img 
                              src={results.pages[dup.page1_idx]?.imageUrl} 
                              alt={`Page ${dup.page1_idx + 1}`}
                              className="w-full h-auto"
                            />
                          </div>
                          <p className="text-xs text-gray-300 p-2">
                            {results.pages[dup.page1_idx]?.text_snippet || "No preview available"}
                          </p>
                        </div>
                        <div className="border border-gray-700 rounded-lg overflow-hidden">
                          <h5 className="text-sm font-medium p-2 bg-gray-800">Page {dup.page2_idx + 1}</h5>
                          <div className="border-t border-b border-gray-700">
                            <img 
                              src={results.pages[dup.page2_idx]?.imageUrl} 
                              alt={`Page ${dup.page2_idx + 1}`}
                              className="w-full h-auto"
                            />
                          </div>
                          <p className="text-xs text-gray-300 p-2">
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
          <div className="bg-black text-white rounded-lg shadow p-6">
            <h3 className="text-xl font-bold mb-4">All Pages</h3>
            
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
              {results.pages.map((page, idx) => {
                // Check if this page is involved in any duplicate
                const isDuplicate = results.duplicates ? 
                  results.duplicates.some(d => d.page1_idx === idx || d.page2_idx === idx) : 
                  false;
                
                return (
                  <div key={idx} className={`border rounded-lg overflow-hidden ${
                    isDuplicate ? 'border-red-500 bg-red-900/20' : 'border-gray-700 bg-gray-900'
                  }`}>
                    <div className="flex justify-between items-center p-2">
                      <h4 className="font-medium">Page {page.page_num}</h4>
                      {isDuplicate && (
                        <span className="text-xs bg-red-500 text-white px-2 py-1 rounded-full">
                          Duplicate
                        </span>
                      )}
                    </div>
                    
                    <div className="border-t border-b border-gray-700">
                      <img 
                        src={page.imageUrl} 
                        alt={`Page ${page.page_num}`}
                        className="w-full h-auto"
                      />
                    </div>
                    
                    <div className="p-2">
                      <p className="text-xs text-gray-300 max-h-20 overflow-hidden">
                        {page.text_snippet || "No preview available"}
                      </p>
                      <div className="mt-2 text-xs text-gray-500 truncate">
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