'use client';

import React, { useState } from 'react';
import UploadDropzone from '../core/UploadDropzone';
import { documentService } from '../../services/documentService';
import { BatchFolderResponse, BatchFolderResult } from '../../types/document';
import type { ReviewData, FlaggedPage } from '../../types/review';

interface Props {
  settings: {
    chunkType: string;
    similarityThreshold: number;
  };
  onComplete?: (data: ReviewData) => void;
}

/**
 * BatchFolder component for analyzing multiple documents for duplicates.
 */
export default function BatchFolder({ settings, onComplete }: Props) {
  const [results, setResults] = useState<BatchFolderResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedResult, setExpandedResult] = useState<number | null>(null);

  // Handle file upload and batch analysis
  const handleUpload = async (files: File | File[]) => {
    const batchFiles: File[] = Array.isArray(files) ? files : [files];

    setIsLoading(true);
    setError(null);
    
    try {
      const result = await documentService.analyzeBatchFolder(batchFiles, settings);
      setResults(result);
      
      // If onComplete callback is provided, format data for review
      if (onComplete) {
        // Create flagged pages array from similar pages
        const flaggedPages: FlaggedPage[] = [];
        
        for (let i = 0; i < result.results.length; i++) {
          flaggedPages.push({
            pageNumber: 1, // Simplified as we're working with whole documents
            pageHash: `${result.results[i].file1}`, // Placeholder for actual hash
            similarity: result.results[i].type === 'exact_duplicate' ? 1.0 : (result.results[i].similarity || 0),
            matchedPage: {
              pageNumber: 1,
              documentId: result.results[i].file2,
              filename: result.results[i].file2
            }
          });
        }
        
        onComplete({
          documentId: `batch-analysis-${Date.now()}`,
          filename: `Batch Analysis (${result.total_documents} documents)`,
          workflowType: 'batch',
          flaggedPages,
          status: 'pending',
          reviewHistory: [],
          duplicateConfidence: result.duplicates_found > 0 ? 0.8 : 0.2
        });
      }
    } catch (error) {
      console.error('Batch analysis failed:', error);
      setError('Failed to analyze documents. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="bg-black text-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold mb-4">Batch Folder Analysis</h3>
        <p className="text-gray-300 mb-4">
          Upload multiple documents to analyze for duplicates across the entire batch.
        </p>
        <UploadDropzone 
          onUpload={handleUpload} 
          mode="multiple"
          label="Upload documents for batch analysis"
          sublabel="Select multiple PDF files (max 50MB each)"
        />
      </div>

      {isLoading && (
        <div className="flex justify-center items-center py-8">
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
          <span className="ml-3 text-gray-600 dark:text-gray-400">Analyzing documents...</span>
        </div>
      )}

      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded dark:bg-red-900/30 dark:text-red-300 dark:border-red-800">
          <p>{error}</p>
        </div>
      )}

      {results && (
        <div className="space-y-6">
          {/* Batch Summary */}
          <div className="bg-black text-white rounded-lg shadow p-6">
            <h3 className="text-xl font-bold mb-4">Batch Analysis Results</h3>
            
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
              <div className="border border-gray-700 rounded-lg p-4 bg-gray-900">
                <h4 className="text-lg font-semibold text-gray-300">Total Documents</h4>
                <p className="text-2xl font-bold">{results.total_documents}</p>
              </div>
              
              <div className="border border-gray-700 rounded-lg p-4 bg-gray-900">
                <h4 className="text-lg font-semibold text-gray-300">Duplicates Found</h4>
                <p className="text-2xl font-bold">{results.duplicates_found}</p>
              </div>
              
              <div className="border border-gray-700 rounded-lg p-4 bg-gray-900">
                <h4 className="text-lg font-semibold text-gray-300">Unique Documents</h4>
                <p className="text-2xl font-bold">{results.total_documents - results.duplicates_found}</p>
              </div>
            </div>
          </div>
          
          {/* Duplicate Results */}
          {results.results.length > 0 ? (
            <div className="bg-black text-white rounded-lg shadow p-6">
              <h3 className="text-xl font-bold mb-4">Duplicate Documents</h3>
              
              <div className="space-y-4">
                {results.results.map((result, idx) => (
                  <div 
                    key={idx}
                    className="bg-gray-900 rounded-lg p-4 border border-gray-700 cursor-pointer hover:bg-gray-800 transition-colors"
                    onClick={() => setExpandedResult(expandedResult === idx ? null : idx)}
                  >
                    <div className="flex justify-between items-center">
                      <div className="flex items-center">
                        <span className={`inline-block w-3 h-3 rounded-full mr-2 ${
                          result.type === 'exact_duplicate' ? 'bg-red-500' : 'bg-yellow-500'
                        }`}></span>
                        <span className="text-sm text-gray-300">
                          {result.type === 'exact_duplicate' ? 'Exact Duplicate' : 'Near Duplicate'}
                        </span>
                      </div>
                      {result.similarity && (
                        <span className={`text-sm ${
                          result.similarity > 0.9 ? 'text-red-400' : 
                          result.similarity > 0.7 ? 'text-yellow-400' : 'text-green-400'
                        }`}>
                          Similarity: {(result.similarity * 100).toFixed(1)}%
                        </span>
                      )}
                    </div>
                    
                    <div className={`grid grid-cols-2 gap-4 overflow-hidden transition-all duration-300 ${
                      expandedResult === idx ? 'max-h-96 mt-4 opacity-100' : 'max-h-0 opacity-0'
                    }`}>
                      <div className="border border-gray-700 rounded-lg p-4 bg-gray-800">
                        <h4 className="font-medium mb-2 text-gray-300">File 1</h4>
                        <p className="text-sm text-white break-all">{result.file1}</p>
                      </div>
                      <div className="border border-gray-700 rounded-lg p-4 bg-gray-800">
                        <h4 className="font-medium mb-2 text-gray-300">File 2</h4>
                        <p className="text-sm text-white break-all">{result.file2}</p>
                      </div>
                      
                      <div className="col-span-2 flex justify-end space-x-3 mt-3">
                        <button className="px-3 py-1 bg-yellow-600 text-white text-sm rounded hover:bg-yellow-700 transition-colors">
                          Compare in Detail
                        </button>
                        <button className="px-3 py-1 bg-red-600 text-white text-sm rounded hover:bg-red-700 transition-colors">
                          Mark as Duplicate
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="bg-black text-white rounded-lg shadow p-6">
              <div className="text-center py-8">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-16 w-16 mx-auto text-green-500 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
                <h3 className="text-xl font-semibold mb-2">No Duplicates Found</h3>
                <p className="text-gray-400">All documents in the batch appear to be unique.</p>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}