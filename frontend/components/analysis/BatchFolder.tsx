'use client';

import React, { useState, useRef } from 'react';
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
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [selectedResults, setSelectedResults] = useState<Set<number>>(new Set());
  const [progress, setProgress] = useState(0);
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  // Track file selection before upload
  const handleFileSelection = (files: File | File[]) => {
    const fileArray = Array.isArray(files) ? files : [files];
    setSelectedFiles(prev => [...prev, ...fileArray]);
  };
  
  // Remove file from selection
  const removeFile = (index: number) => {
    setSelectedFiles(prev => prev.filter((_, i) => i !== index));
  };
  
  // Handle file upload and batch analysis
  const handleUpload = async () => {
    if (selectedFiles.length === 0) return;
    
    setIsLoading(true);
    setError(null);
    setProgress(0);
    
    try {
      // Mock progress updates (in a real implementation, you'd use proper upload progress events)
      const progressInterval = setInterval(() => {
        setProgress(prev => {
          const newProgress = prev + (5 * Math.random());
          return newProgress >= 95 ? 95 : newProgress;
        });
      }, 200);
      
      const result = await documentService.analyzeBatchFolder(selectedFiles, settings);
      clearInterval(progressInterval);
      setProgress(100);
      setResults(result);
      
      // If onComplete callback is provided, format data for review
      if (onComplete) {
        const flaggedPages: FlaggedPage[] = [];
        
        for (let i = 0; i < result.results.length; i++) {
          flaggedPages.push({
            pageNumber: 1,
            pageHash: `${result.results[i].file1}`,
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
      setProgress(0);
    }
  };
  
  // Toggle selection of a result item
  const toggleResultSelection = (idx: number) => {
    const newSelected = new Set(selectedResults);
    if (newSelected.has(idx)) {
      newSelected.delete(idx);
    } else {
      newSelected.add(idx);
    }
    setSelectedResults(newSelected);
  };
  
  // Batch actions on selected results
  const markAllSelectedAsDuplicates = () => {
    if (selectedResults.size === 0 || !results) return;
    
    alert(`Marked ${selectedResults.size} items as duplicates`);
    // Implementation would update status in backend
  };
  
  // Export results to CSV
  const exportResults = () => {
    if (!results) return;
    
    const csvContent = [
      // CSV header
      'File 1,File 2,Match Type,Similarity',
      // Data rows
      ...results.results.map(r => 
        `"${r.file1}","${r.file2}","${r.type}",${r.similarity || 1.0}`
      )
    ].join('\n');
    
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `duplicate-analysis-${new Date().toISOString()}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  return (
    <div className="space-y-6">
      <div className="bg-black text-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold mb-4">Batch Document Management</h3>
        
        {/* File Selection State */}
        {selectedFiles.length === 0 ? (
          <>
            <p className="text-gray-300 mb-4">
              Upload multiple documents to analyze for duplicates across the entire batch.
            </p>
            <UploadDropzone 
              mode="multiple"
              label="Select documents for batch analysis"
              sublabel="Select multiple PDF files (max 50MB each)"
              onUpload={handleFileSelection}
            />
          </>
        ) : (
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <h4 className="font-medium">Selected Files ({selectedFiles.length})</h4>
              <div className="space-x-2">
                <button 
                  onClick={() => fileInputRef.current?.click()}
                  className="px-2 py-1 bg-gray-700 text-white text-sm rounded hover:bg-gray-600"
                >
                  Add More
                </button>
                <button 
                  onClick={() => setSelectedFiles([])}
                  className="px-2 py-1 bg-red-700 text-white text-sm rounded hover:bg-red-600"
                >
                  Clear All
                </button>
              </div>
            </div>
            
            <div className="max-h-60 overflow-y-auto bg-gray-900 rounded-lg p-2">
              <table className="w-full text-sm">
                <thead className="text-gray-400 border-b border-gray-700">
                  <tr>
                    <th className="text-left py-2 px-3">Filename</th>
                    <th className="text-right py-2 px-3">Size</th>
                    <th className="text-right py-2 px-3">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {selectedFiles.map((file, idx) => (
                    <tr key={idx} className="border-b border-gray-800">
                      <td className="py-2 px-3 truncate max-w-xs">{file.name}</td>
                      <td className="text-right py-2 px-3 whitespace-nowrap">
                        {(file.size / 1024 / 1024).toFixed(2)} MB
                      </td>
                      <td className="text-right py-2 px-3">
                        <button 
                          onClick={() => removeFile(idx)}
                          className="text-red-400 hover:text-red-300"
                        >
                          Remove
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            
            <div className="flex justify-end">
              <button
                onClick={handleUpload}
                disabled={isLoading}
                className="px-4 py-2 bg-blue-600 text-white font-medium rounded hover:bg-blue-700 disabled:opacity-50"
              >
                {isLoading ? 'Analyzing...' : 'Analyze Batch'}
              </button>
            </div>
          </div>
        )}
        
        <input
          type="file"
          ref={fileInputRef}
          className="hidden"
          multiple
          accept=".pdf"
          onChange={(e) => {
            if (e.target.files?.length) {
              handleFileSelection(Array.from(e.target.files));
            }
          }}
        />
      </div>

      {isLoading && (
        <div className="bg-gray-900 rounded-lg p-6">
          <div className="mb-2 flex justify-between">
            <span className="text-gray-300">Analyzing documents...</span>
            <span className="text-gray-300">{Math.round(progress)}%</span>
          </div>
          <div className="w-full bg-gray-700 rounded-full h-2.5">
            <div 
              className="bg-blue-600 h-2.5 rounded-full transition-all duration-300" 
              style={{ width: `${progress}%` }}
            ></div>
          </div>
        </div>
      )}

      {error && (
        <div className="bg-red-900/30 border border-red-800 text-red-300 px-4 py-3 rounded">
          <p>{error}</p>
        </div>
      )}

      {results && (
        <div className="space-y-6">
          {/* Batch Summary */}
          <div className="bg-black text-white rounded-lg shadow p-6">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-xl font-bold">Batch Analysis Results</h3>
              <button
                onClick={exportResults}
                className="px-3 py-1 bg-green-700 text-white text-sm rounded hover:bg-green-600 flex items-center"
              >
                <span>Export CSV</span>
              </button>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
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
              
              <div className="border border-gray-700 rounded-lg p-4 bg-gray-900">
                <h4 className="text-lg font-semibold text-gray-300">Similarity Avg</h4>
                <p className="text-2xl font-bold">
                  {results.results.length > 0 
                    ? (results.results.reduce((sum, r) => sum + (r.similarity || 1.0), 0) / results.results.length * 100).toFixed(1) + '%'
                    : 'N/A'}
                </p>
              </div>
            </div>
          </div>
          
          {/* Duplicate Results with Batch Actions */}
          {results.results.length > 0 ? (
            <div className="bg-black text-white rounded-lg shadow p-6">
              <div className="flex justify-between items-center mb-4">
                <h3 className="text-xl font-bold">Duplicate Documents</h3>
                <div className="flex space-x-2">
                  <button
                    onClick={markAllSelectedAsDuplicates}
                    disabled={selectedResults.size === 0}
                    className="px-3 py-1 bg-red-700 text-white text-sm rounded hover:bg-red-600 disabled:opacity-50"
                  >
                    Mark Selected as Duplicates
                  </button>
                </div>
              </div>
              
              <div className="space-y-4">
                {results.results.map((result, idx) => (
                  <div 
                    key={idx}
                    className={`bg-gray-900 rounded-lg p-4 border ${
                      selectedResults.has(idx) ? 'border-blue-500' : 'border-gray-700'
                    } hover:bg-gray-800 transition-colors`}
                  >
                    <div className="flex justify-between items-center">
                      <div className="flex items-center">
                        <input
                          type="checkbox"
                          checked={selectedResults.has(idx)}
                          onChange={() => toggleResultSelection(idx)}
                          className="mr-3 h-4 w-4 rounded"
                          onClick={(e) => e.stopPropagation()}
                        />
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
                      <button 
                        onClick={() => setExpandedResult(expandedResult === idx ? null : idx)}
                        className="text-gray-400 hover:text-white"
                      >
                        {expandedResult === idx ? 'Collapse' : 'Expand'}
                      </button>
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