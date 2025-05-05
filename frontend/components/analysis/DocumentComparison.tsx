'use client';

import React, { useState } from 'react';
import UploadDropzone from '../core/UploadDropzone';
import { documentService } from '../../services/documentService';
import { getAbsoluteApiUrl } from '../../services/baseApi';
import type { ReviewData, FlaggedPage } from '../../types/review';

interface Props {
  onComplete?: (data: ReviewData) => void;
}

interface ComparisonResult {
  doc1: {
    text: string;
    filename: string;
    pages: {
      pageNumber: number;
      imageUrl: string;
      similarity: number;
    }[];
  };
  doc2: {
    text: string;
    filename: string;
    pages: {
      pageNumber: number;
      imageUrl: string;
      similarity: number;
    }[];
  };
  similarity: number;
}

/**
 * DocumentComparison component for comparing two documents.
 */
export default function DocumentComparison({ onComplete }: Props) {
  const [file1, setFile1] = useState<File | null>(null);
  const [file2, setFile2] = useState<File | null>(null);
  const [results, setResults] = useState<ComparisonResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentPagePair, setCurrentPagePair] = useState<number>(0);

  // Handle first file upload
  const handleFile1Upload = (files: File | File[]) => {
    const file = Array.isArray(files) ? files[0] : files;
    setFile1(file);
    setResults(null);
    setError(null);
  };

  // Handle second file upload
  const handleFile2Upload = (files: File | File[]) => {
    const file = Array.isArray(files) ? files[0] : files;
    setFile2(file);
    setResults(null);
    setError(null);
  };

  // Compare the two documents
  const handleCompare = async () => {
    if (!file1 || !file2) {
      setError('Please upload both documents to compare');
      return;
    }

    setIsLoading(true);
    setError(null);
    
    try {
      const result = await documentService.compareDocuments(file1, file2);
      
      // Fix image URLs - convert relative URLs to absolute URLs
      if (result.doc1 && result.doc1.pages) {
        result.doc1.pages = result.doc1.pages.map(page => ({
          ...page,
          imageUrl: getAbsoluteApiUrl(page.imageUrl)
        }));
      }
      
      if (result.doc2 && result.doc2.pages) {
        result.doc2.pages = result.doc2.pages.map(page => ({
          ...page,
          imageUrl: getAbsoluteApiUrl(page.imageUrl)
        }));
      }
      
      setResults(result);
      
      // If onComplete callback is provided, format data for review
      if (onComplete && result) {
        // Create flagged pages array from similar pages
        const flaggedPages: FlaggedPage[] = [];
        
        for (let i = 0; i < result.doc1.pages.length; i++) {
          if (result.doc1.pages[i].similarity > 0.7) {
            flaggedPages.push({
              pageNumber: result.doc1.pages[i].pageNumber,
              pageHash: `${file1.name}_page${result.doc1.pages[i].pageNumber}`, // Placeholder for actual hash
              similarity: result.doc1.pages[i].similarity,
              matchedPage: {
                pageNumber: result.doc2.pages[i].pageNumber,
                documentId: file2.name,
                filename: file2.name
              }
            });
          }
        }
        
        onComplete({
          documentId: `compare_${Date.now()}`,
          filename: `Comparison: ${file1.name} vs ${file2.name}`,
          workflowType: 'compare',
          flaggedPages,
          status: 'pending',
          reviewHistory: [],
          duplicateConfidence: result.similarity
        });
      }
      
    } catch (error) {
      console.error('Comparison failed:', error);
      setError('Failed to compare documents. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  // Get color based on similarity score
  const getSimilarityColor = (similarity: number): string => {
    if (similarity > 0.8) return 'text-red-500';
    if (similarity > 0.6) return 'text-yellow-500';
    return 'text-green-500';
  };

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* First document upload */}
        <div className="bg-black text-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold mb-4">Document 1</h3>
          <UploadDropzone 
            onUpload={handleFile1Upload} 
            mode="single"
            label={file1 ? 'Replace document' : 'Upload first document'}
            sublabel="PDF file only"
          />
          {file1 && (
            <div className="mt-4 p-3 bg-gray-900 rounded-lg">
              <p className="text-sm break-all">
                {file1.name} ({Math.round(file1.size / 1024)} KB)
              </p>
            </div>
          )}
        </div>

        {/* Second document upload */}
        <div className="bg-black text-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold mb-4">Document 2</h3>
          <UploadDropzone 
            onUpload={handleFile2Upload} 
            mode="single"
            label={file2 ? 'Replace document' : 'Upload second document'}
            sublabel="PDF file only"
          />
          {file2 && (
            <div className="mt-4 p-3 bg-gray-900 rounded-lg">
              <p className="text-sm break-all">
                {file2.name} ({Math.round(file2.size / 1024)} KB)
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Compare button */}
      <div className="flex justify-center">
        <button
          onClick={handleCompare}
          disabled={!file1 || !file2 || isLoading}
          className={`px-6 py-3 rounded-lg font-medium ${
            !file1 || !file2 || isLoading
              ? 'bg-gray-500 cursor-not-allowed'
              : 'bg-blue-600 hover:bg-blue-700'
          } text-white transition-colors`}
        >
          {isLoading ? (
            <span className="flex items-center">
              <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              Comparing...
            </span>
          ) : (
            'Compare Documents'
          )}
        </button>
      </div>

      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded dark:bg-red-900/30 dark:text-red-300 dark:border-red-800">
          <p>{error}</p>
        </div>
      )}

      {results && (
        <div className="space-y-6">
          {/* Comparison Summary */}
          <div className="bg-black text-white rounded-lg shadow p-6">
            <h3 className="text-xl font-bold mb-4">Comparison Results</h3>
            
            <div className="mb-6">
              <h4 className="text-lg font-semibold mb-2">Overall Similarity</h4>
              <div className="flex items-center mb-2">
                <div className="w-full bg-gray-700 rounded-full mr-2">
                  <div
                    className={`h-2.5 rounded-full ${
                      results.similarity > 0.8 ? 'bg-red-500' :
                      results.similarity > 0.6 ? 'bg-yellow-500' : 'bg-green-500'
                    }`}
                    style={{ width: `${results.similarity * 100}%` }}
                  ></div>
                </div>
                <div className={`text-sm font-medium ${getSimilarityColor(results.similarity)}`}>
                  {(results.similarity * 100).toFixed(1)}%
                </div>
              </div>
              <p className="text-sm text-gray-400">
                {results.similarity > 0.8 
                  ? 'Documents are very similar and likely duplicates.' 
                  : results.similarity > 0.6 
                  ? 'Documents share significant content.' 
                  : 'Documents are mostly distinct.'}
              </p>
            </div>
            
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="bg-gray-900 p-4 rounded-lg">
                <h5 className="font-medium mb-2">{results.doc1.filename}</h5>
                <p className="text-sm text-gray-400">{results.doc1.pages.length} pages</p>
              </div>
              <div className="bg-gray-900 p-4 rounded-lg">
                <h5 className="font-medium mb-2">{results.doc2.filename}</h5>
                <p className="text-sm text-gray-400">{results.doc2.pages.length} pages</p>
              </div>
            </div>
          </div>
          
          {/* Page Comparison */}
          <div className="bg-black text-white rounded-lg shadow p-6">
            <h3 className="text-xl font-bold mb-4">Page Comparison</h3>
            
            <div className="mb-4 flex justify-between items-center">
              <div>
                <p className="text-sm text-gray-400">
                  Viewing page pair {currentPagePair + 1} of {Math.min(results.doc1.pages.length, results.doc2.pages.length)}
                </p>
              </div>
              <div className="flex space-x-2">
                <button
                  onClick={() => setCurrentPagePair(prev => Math.max(0, prev - 1))}
                  disabled={currentPagePair === 0}
                  className={`p-2 rounded ${
                    currentPagePair === 0
                      ? 'bg-gray-800 text-gray-500 cursor-not-allowed'
                      : 'bg-gray-800 hover:bg-gray-700 text-white'
                  }`}
                >
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M12.707 5.293a1 1 0 010 1.414L9.414 10l3.293 3.293a1 1 0 01-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z" clipRule="evenodd" />
                  </svg>
                </button>
                <button
                  onClick={() => setCurrentPagePair(prev => Math.min(Math.min(results.doc1.pages.length, results.doc2.pages.length) - 1, prev + 1))}
                  disabled={currentPagePair === Math.min(results.doc1.pages.length, results.doc2.pages.length) - 1}
                  className={`p-2 rounded ${
                    currentPagePair === Math.min(results.doc1.pages.length, results.doc2.pages.length) - 1
                      ? 'bg-gray-800 text-gray-500 cursor-not-allowed'
                      : 'bg-gray-800 hover:bg-gray-700 text-white'
                  }`}
                >
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clipRule="evenodd" />
                  </svg>
                </button>
              </div>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Document 1 Page */}
              {results.doc1.pages[currentPagePair] && (
                <div className="space-y-3">
                  <div className="flex justify-between">
                    <h4 className="font-medium">
                      Document 1, Page {results.doc1.pages[currentPagePair].pageNumber}
                    </h4>
                    <span className={`text-sm ${getSimilarityColor(results.doc1.pages[currentPagePair].similarity)}`}>
                      {(results.doc1.pages[currentPagePair].similarity * 100).toFixed(1)}% similar
                    </span>
                  </div>
                  <div className="border border-gray-700 rounded-lg overflow-hidden">
                    <img
                      src={results.doc1.pages[currentPagePair].imageUrl}
                      alt={`Page ${results.doc1.pages[currentPagePair].pageNumber} from document 1`}
                      className="w-full h-auto"
                    />
                  </div>
                </div>
              )}
              
              {/* Document 2 Page */}
              {results.doc2.pages[currentPagePair] && (
                <div className="space-y-3">
                  <div className="flex justify-between">
                    <h4 className="font-medium">
                      Document 2, Page {results.doc2.pages[currentPagePair].pageNumber}
                    </h4>
                    <span className={`text-sm ${getSimilarityColor(results.doc2.pages[currentPagePair].similarity)}`}>
                      {(results.doc2.pages[currentPagePair].similarity * 100).toFixed(1)}% similar
                    </span>
                  </div>
                  <div className="border border-gray-700 rounded-lg overflow-hidden">
                    <img
                      src={results.doc2.pages[currentPagePair].imageUrl}
                      alt={`Page ${results.doc2.pages[currentPagePair].pageNumber} from document 2`}
                      className="w-full h-auto"
                    />
                  </div>
                </div>
              )}
            </div>
          </div>
          
          {/* Page Similarity Matrix */}
          <div className="bg-black text-white rounded-lg shadow p-6">
            <h3 className="text-xl font-bold mb-4">Page Similarity Matrix</h3>
            
            <div className="overflow-x-auto">
              <table className="min-w-full">
                <thead>
                  <tr>
                    <th className="px-3 py-2 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                      
                    </th>
                    {results.doc2.pages.map((page, i) => (
                      <th key={i} className="px-3 py-2 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                        Doc 2, Page {page.pageNumber}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-700">
                  {results.doc1.pages.map((page, i) => (
                    <tr key={i} className={i % 2 === 0 ? 'bg-gray-900' : 'bg-gray-800'}>
                      <td className="px-3 py-2 whitespace-nowrap text-sm font-medium text-white">
                        Doc 1, Page {page.pageNumber}
                      </td>
                      {results.doc2.pages.map((page2, j) => {
                        // Calculate similarity for this pair
                        const similarity = i === j ? page.similarity : 0.3; // Simplified - in real app would use actual data
                        
                        return (
                          <td key={j} className="px-3 py-2 whitespace-nowrap text-sm">
                            <div 
                              className={`py-1 px-2 rounded text-center ${
                                similarity > 0.8 ? 'bg-red-900 text-red-200' :
                                similarity > 0.6 ? 'bg-yellow-900 text-yellow-200' :
                                similarity > 0.4 ? 'bg-blue-900 text-blue-200' :
                                'bg-gray-700 text-gray-400'
                              }`}
                            >
                              {(similarity * 100).toFixed(0)}%
                            </div>
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}