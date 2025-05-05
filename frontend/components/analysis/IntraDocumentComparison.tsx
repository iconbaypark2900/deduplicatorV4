'use client';

import React, { useState } from 'react';
import UploadDropzone from '../core/UploadDropzone';
import { documentService } from '../../services/documentService';
import { getAbsoluteApiUrl } from '../../services/baseApi';
import type { ReviewData, FlaggedPage } from '../../types/review';

interface Props {
  onComplete?: (data: ReviewData) => void;
}

interface PageData {
  pageNumber: number;
  imageUrl: string;
  text?: string;
}

interface SimilarityPair {
  page1: number;
  page2: number;
  similarity: number;
}

interface IntraComparisonResult {
  filename: string;
  pages: PageData[];
  similarityMatrix: SimilarityPair[];
  highSimilarityPairs: SimilarityPair[];
}

/**
 * IntraDocumentComparison component for comparing pages within a single document.
 */
export default function IntraDocumentComparison({ onComplete }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [results, setResults] = useState<IntraComparisonResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentPair, setCurrentPair] = useState<number>(0);
  const [threshold, setThreshold] = useState<number>(0.7);

  // Handle file upload
  const handleFileUpload = (files: File | File[]) => {
    const file = Array.isArray(files) ? files[0] : files;
    setFile(file);
    setResults(null);
    setError(null);
  };

  // Analyze the document for internal similarities
  const handleAnalyze = async () => {
    if (!file) {
      setError('Please upload a document to analyze');
      return;
    }

    setIsLoading(true);
    setError(null);
    
    try {
      // Start the timer to track how long the analysis takes
      const startTime = Date.now();
      
      // Perform the analysis
      const result = await documentService.analyzeIntraDocument(file, threshold);
      
      // Calculate how long it took
      const processingTime = ((Date.now() - startTime) / 1000).toFixed(1);
      console.log(`Document analysis completed in ${processingTime} seconds`);
      
      // Fix image URLs - convert relative URLs to absolute URLs
      if (result.pages) {
        result.pages = result.pages.map(page => ({
          ...page,
          imageUrl: getAbsoluteApiUrl(page.imageUrl)
        }));
      }
      
      console.log('Processed result pages with absolute URLs:', result.pages);
      console.log('Medical confidence from API:', result.medicalConfidence);
      
      setResults(result);
      
      // If onComplete callback is provided, format data for review
      if (onComplete && result) {
        // Create flagged pages array from similar pages
        const flaggedPages: FlaggedPage[] = [];
        
        for (const pair of result.highSimilarityPairs) {
          // Get the image URLs from the results
          const page1 = result.pages.find(p => p.pageNumber === pair.page1);
          const page2 = result.pages.find(p => p.pageNumber === pair.page2);
          
          if (!page1 || !page2) {
            console.error(`Couldn't find page data for page ${pair.page1} or ${pair.page2}`);
            continue;
          }
          
          const page1Image = page1.imageUrl;
          const page2Image = page2.imageUrl;
          
          // The imageUrls in result.pages should already be absolute URLs
          // after the transformation done earlier, but let's ensure that
          console.log('Page 1 image URL:', page1Image);
          console.log('Page 2 image URL:', page2Image);
          
          // Ensure both image URLs are absolute URLs
          const page1AbsoluteUrl = page1Image ? (page1Image.startsWith('http') ? page1Image : getAbsoluteApiUrl(page1Image)) : null;
          const page2AbsoluteUrl = page2Image ? (page2Image.startsWith('http') ? page2Image : getAbsoluteApiUrl(page2Image)) : null;
          
          console.log('Page 1 absolute URL:', page1AbsoluteUrl);
          console.log('Page 2 absolute URL:', page2AbsoluteUrl);
          
          flaggedPages.push({
            pageNumber: pair.page1,
            pageHash: `${file.name}_page${pair.page1}`, // Placeholder for actual hash
            similarity: pair.similarity,
            imageUrl: page1AbsoluteUrl,
            matchedPage: {
              pageNumber: pair.page2,
              documentId: file.name,
              filename: file.name,
              imageUrl: page2AbsoluteUrl,
              pageHash: `${file.name}_page${pair.page2}` // Add pageHash for fallback URL
            }
          });
        }
        
        console.log('Flagged pages for review:', flaggedPages);
        
        onComplete({
          documentId: `intra_${Date.now()}`,
          filename: `Intra-Document Analysis: ${file.name}`,
          workflowType: 'intra-compare',
          flaggedPages,
          status: 'pending',
          reviewHistory: [],
          medicalConfidence: result.medicalConfidence || 0,
          duplicateConfidence: flaggedPages.length > 0 ? 
            flaggedPages.reduce((acc, page) => acc + page.similarity, 0) / flaggedPages.length : 
            0
        });
      }
      
    } catch (error: any) {
      console.error('Analysis failed:', error);
      
      // Provide more specific error messages based on the error type
      if (error.message && error.message.includes('timeout')) {
        setError('The analysis timed out. Your document may be too large or complex. Try a smaller document or adjust the threshold.');
      } else if (error.status === 413) {
        setError('Document is too large. Please try with a smaller file.');
      } else if (error.status === 400) {
        setError(`Analysis failed: ${error.message || 'Invalid document format or content'}`);
      } else if (error.status === 500) {
        setError('Server error during analysis. Please try again later.');
      } else {
        setError(`Failed to analyze document: ${error.message || 'Unknown error'}`);
      }
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
      <div>
        {/* Document upload */}
        <div className="bg-black text-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold mb-4">Upload Document</h3>
          <UploadDropzone 
            onUpload={handleFileUpload} 
            mode="single"
            label={file ? 'Replace document' : 'Upload document'}
            sublabel="PDF file only"
          />
          {file && (
            <div className="mt-4 p-3 bg-gray-900 rounded-lg">
              <p className="text-sm break-all">
                {file.name} ({Math.round(file.size / 1024)} KB)
              </p>
            </div>
          )}
        </div>

        {/* Threshold slider */}
        <div className="mt-4 bg-black text-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold mb-4">Similarity Threshold</h3>
          <div className="flex items-center">
            <input
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={threshold}
              onChange={(e) => setThreshold(parseFloat(e.target.value))}
              className="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer"
            />
            <span className="ml-4 text-sm font-medium">
              {(threshold * 100).toFixed(0)}%
            </span>
          </div>
          <p className="mt-2 text-sm text-gray-400">
            Pages with similarity scores above this threshold will be flagged as potential duplicates.
          </p>
        </div>
      </div>

      {/* Analyze button */}
      <div className="flex justify-center">
        <button
          onClick={handleAnalyze}
          disabled={!file || isLoading}
          className={`px-6 py-3 rounded-lg font-medium ${
            !file || isLoading
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
              <div>
                <div>Analyzing... This may take several minutes</div>
                <div className="text-xs text-gray-300">Please do not close this window</div>
              </div>
            </span>
          ) : (
            'Analyze Document'
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
          {/* Analysis Summary */}
          <div className="bg-black text-white rounded-lg shadow p-6">
            <h3 className="text-xl font-bold mb-4">Analysis Results</h3>
            
            <div className="mb-6">
              <h4 className="text-lg font-semibold mb-2">Document Overview</h4>
              <div className="bg-gray-900 p-4 rounded-lg">
                <h5 className="font-medium mb-2">{results.filename}</h5>
                <p className="text-sm text-gray-400">{results.pages.length} pages</p>
                <p className="text-sm text-gray-400">
                  {results.highSimilarityPairs.length} pairs of pages with similarity above {(threshold * 100).toFixed(0)}%
                </p>
              </div>
            </div>
          </div>
          
          {/* Similar Page Pairs */}
          {results.highSimilarityPairs.length > 0 && (
            <div className="bg-black text-white rounded-lg shadow p-6">
              <h3 className="text-xl font-bold mb-4">Similar Page Pairs</h3>
              
              <div className="mb-4 flex justify-between items-center">
                <div>
                  <p className="text-sm text-gray-400">
                    Viewing pair {currentPair + 1} of {results.highSimilarityPairs.length}
                  </p>
                </div>
                <div className="flex space-x-2">
                  <button
                    onClick={() => setCurrentPair(prev => Math.max(0, prev - 1))}
                    disabled={currentPair === 0}
                    className={`p-2 rounded ${
                      currentPair === 0
                        ? 'bg-gray-800 text-gray-500 cursor-not-allowed'
                        : 'bg-gray-800 hover:bg-gray-700 text-white'
                    }`}
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                      <path fillRule="evenodd" d="M12.707 5.293a1 1 0 010 1.414L9.414 10l3.293 3.293a1 1 0 01-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z" clipRule="evenodd" />
                    </svg>
                  </button>
                  <button
                    onClick={() => setCurrentPair(prev => Math.min(results.highSimilarityPairs.length - 1, prev + 1))}
                    disabled={currentPair === results.highSimilarityPairs.length - 1}
                    className={`p-2 rounded ${
                      currentPair === results.highSimilarityPairs.length - 1
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
              
              {results.highSimilarityPairs[currentPair] && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {/* Page 1 */}
                  <div className="space-y-3">
                    <div className="flex justify-between">
                      <h4 className="font-medium">
                        Page {results.highSimilarityPairs[currentPair].page1}
                      </h4>
                      <span className={`text-sm ${getSimilarityColor(results.highSimilarityPairs[currentPair].similarity)}`}>
                        {(results.highSimilarityPairs[currentPair].similarity * 100).toFixed(1)}% similar
                      </span>
                    </div>
                    <div className="border border-gray-700 rounded-lg overflow-hidden">
                      <img
                        src={results.pages.find(p => p.pageNumber === results.highSimilarityPairs[currentPair].page1)?.imageUrl}
                        alt={`Page ${results.highSimilarityPairs[currentPair].page1}`}
                        className="w-full h-auto"
                      />
                    </div>
                  </div>
                  
                  {/* Page 2 */}
                  <div className="space-y-3">
                    <div className="flex justify-between">
                      <h4 className="font-medium">
                        Page {results.highSimilarityPairs[currentPair].page2}
                      </h4>
                      <span className={`text-sm ${getSimilarityColor(results.highSimilarityPairs[currentPair].similarity)}`}>
                        {(results.highSimilarityPairs[currentPair].similarity * 100).toFixed(1)}% similar
                      </span>
                    </div>
                    <div className="border border-gray-700 rounded-lg overflow-hidden">
                      <img
                        src={results.pages.find(p => p.pageNumber === results.highSimilarityPairs[currentPair].page2)?.imageUrl}
                        alt={`Page ${results.highSimilarityPairs[currentPair].page2}`}
                        className="w-full h-auto"
                      />
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
          
          {/* Page Similarity Matrix */}
          <div className="bg-black text-white rounded-lg shadow p-6">
            <h3 className="text-xl font-bold mb-4">Page Similarity Matrix</h3>
            
            <div className="overflow-x-auto">
              <table className="min-w-full">
                <thead>
                  <tr>
                    <th className="px-3 py-2 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                      
                    </th>
                    {results.pages.map((page) => (
                      <th key={page.pageNumber} className="px-3 py-2 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                        Page {page.pageNumber}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-700">
                  {results.pages.map((page, i) => (
                    <tr key={page.pageNumber} className={i % 2 === 0 ? 'bg-gray-900' : 'bg-gray-800'}>
                      <td className="px-3 py-2 whitespace-nowrap text-sm font-medium text-white">
                        Page {page.pageNumber}
                      </td>
                      {results.pages.map((otherPage) => {
                        // Find similarity for this pair in the matrix
                        const pairData = results.similarityMatrix.find(
                          p => (p.page1 === page.pageNumber && p.page2 === otherPage.pageNumber) ||
                               (p.page2 === page.pageNumber && p.page1 === otherPage.pageNumber)
                        );
                        
                        const similarity = page.pageNumber === otherPage.pageNumber ? 
                          1.0 : // Same page has 100% similarity
                          pairData?.similarity || 0;
                        
                        return (
                          <td key={otherPage.pageNumber} className="px-3 py-2 whitespace-nowrap text-sm">
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