'use client';

import React, { useState } from 'react';
import { ReviewData, WorkflowType, ReviewStatus, ReviewDecision, ReviewHistoryEntry, FlaggedPage } from '../../types/review';

interface ReviewProps {
  docId: string;
  filename: string;
  workflowType: WorkflowType;
  flaggedPages: FlaggedPage[];
  medicalConfidence?: number;
  duplicateConfidence?: number;
  status: ReviewStatus;
  reviewHistory: ReviewHistoryEntry[];
  lastReviewer?: string;
  lastReviewedAt?: string;
  onDocumentAction: (documentId: string, decision: ReviewDecision, notes?: string) => void;
  onComplete?: () => void;
}

/**
 * Review component for manually reviewing document analysis results.
 * Supports decision-making and tracking review history.
 */
export default function Review({
  docId,
  filename,
  workflowType,
  flaggedPages,
  medicalConfidence = 0,
  duplicateConfidence = 0,
  status,
  reviewHistory,
  lastReviewer,
  lastReviewedAt,
  onDocumentAction,
  onComplete
}: ReviewProps) {
  const [notes, setNotes] = useState("");
  const [selectedPage, setSelectedPage] = useState<number | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  
  // Format date for display
  const formatDate = (dateString?: string) => {
    if (!dateString) return "N/A";
    return new Date(dateString).toLocaleString();
  };
  
  // Handle document decision
  const handleDecision = async (decision: ReviewDecision) => {
    setIsProcessing(true);
    try {
      await onDocumentAction(docId, decision, notes);
      if (onComplete) {
        onComplete();
      }
    } catch (error) {
      console.error("Error during review action:", error);
    } finally {
      setIsProcessing(false);
    }
  };
  
  // Get status badge color
  const getStatusColor = (status: ReviewStatus) => {
    switch (status) {
      case 'reviewed':
        return 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300';
      case 'archived':
        return 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300';
      default:
        return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300';
    }
  };
  
  // Get appropriate workflow icon
  const getWorkflowIcon = () => {
    switch (workflowType) {
      case 'compare':
        return (
          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M4 2a2 2 0 00-2 2v11a3 3 0 106 0V4a2 2 0 00-2-2H4zm1 14a1 1 0 100-2 1 1 0 000 2zm5-1.757l4.9-4.9a2 2 0 000-2.828L13.485 5.1a2 2 0 00-2.828 0L10 5.757v8.486zM16 18H9.071l6-6H16a2 2 0 012 2v2a2 2 0 01-2 2z" clipRule="evenodd" />
          </svg>
        );
      case 'single':
        return (
          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z" clipRule="evenodd" />
          </svg>
        );
      case 'batch':
        return (
          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
            <path d="M7 3a1 1 0 000 2h6a1 1 0 100-2H7zM4 7a1 1 0 011-1h10a1 1 0 110 2H5a1 1 0 01-1-1zM2 11a2 2 0 012-2h12a2 2 0 012 2v4a2 2 0 01-2 2H4a2 2 0 01-2-2v-4z" />
          </svg>
        );
      case 'medical':
        return (
          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M3.172 5.172a4 4 0 015.656 0L10 6.343l1.172-1.171a4 4 0 115.656 5.656L10 17.657l-6.828-6.829a4 4 0 010-5.656z" clipRule="evenodd" />
          </svg>
        );
      case 'cluster':
        return (
          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
            <path d="M13 7H7v6h6V7z" />
            <path fillRule="evenodd" d="M7 2a1 1 0 012 0v1h2V2a1 1 0 112 0v1h2a2 2 0 012 2v2h1a1 1 0 110 2h-1v2h1a1 1 0 110 2h-1v2a2 2 0 01-2 2h-2v1a1 1 0 11-2 0v-1H9v1a1 1 0 11-2 0v-1H5a2 2 0 01-2-2v-2H2a1 1 0 110-2h1V9H2a1 1 0 010-2h1V5a2 2 0 012-2h2V2zM5 5h10v10H5V5z" clipRule="evenodd" />
          </svg>
        );
      case 'content':
        return (
          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M3 5a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zM3 10a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zM3 15a1 1 0 011-1h6a1 1 0 110 2H4a1 1 0 01-1-1z" clipRule="evenodd" />
          </svg>
        );
      default:
        return (
          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z" clipRule="evenodd" />
          </svg>
        );
    }
  };

  return (
    <div className="space-y-6">
      {/* Document header */}
      <div className="bg-black text-white rounded-lg p-6">
        <div className="flex justify-between items-start">
          <div className="flex items-center">
            <div className="mr-3 text-gray-400">
              {getWorkflowIcon()}
            </div>
            <div>
              <h1 className="text-xl font-bold">{filename}</h1>
              <p className="text-gray-400 text-sm">ID: {docId}</p>
              <div className="mt-1">
                <span className={`inline-block text-xs px-2 py-1 rounded ${getStatusColor(status)}`}>
                  {status === 'pending' ? 'Pending Review' : 
                   status === 'reviewed' ? 'Reviewed' : 'Archived'}
                </span>
              </div>
            </div>
          </div>
          
          {lastReviewer && (
            <div className="text-right text-sm">
              <p className="text-gray-400">Last reviewed by:</p>
              <p className="text-white">{lastReviewer}</p>
              <p className="text-gray-400 text-xs">{formatDate(lastReviewedAt)}</p>
            </div>
          )}
        </div>
      </div>

      {/* Confidence Scores */}
      <div className="bg-black text-white rounded-lg p-6">
        <h2 className="text-lg font-bold mb-4">Document Confidence</h2>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Medical Confidence */}
          {medicalConfidence > 0 && (
            <div>
              <div className="flex justify-between items-center mb-2">
                <span className="text-gray-400">Medical Content</span>
                <span className="text-white font-medium">{(medicalConfidence * 100).toFixed(0)}%</span>
              </div>
              <div className="w-full bg-gray-700 rounded-full h-3">
                <div 
                  className={`h-3 rounded-full ${
                    medicalConfidence > 0.7 ? 'bg-green-500' : 
                    medicalConfidence > 0.4 ? 'bg-yellow-500' : 'bg-red-500'
                  }`}
                  style={{ width: `${(medicalConfidence * 100).toFixed(0)}%` }}
                ></div>
              </div>
            </div>
          )}
          
          {/* Duplicate Confidence */}
          {duplicateConfidence > 0 && (
            <div>
              <div className="flex justify-between items-center mb-2">
                <span className="text-gray-400">Duplicate Likelihood</span>
                <span className="text-white font-medium">{(duplicateConfidence * 100).toFixed(0)}%</span>
              </div>
              <div className="w-full bg-gray-700 rounded-full h-3">
                <div 
                  className={`h-3 rounded-full ${
                    duplicateConfidence > 0.7 ? 'bg-red-500' : 
                    duplicateConfidence > 0.4 ? 'bg-yellow-500' : 'bg-green-500'
                  }`}
                  style={{ width: `${(duplicateConfidence * 100).toFixed(0)}%` }}
                ></div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Flagged Pages */}
      {flaggedPages && flaggedPages.length > 0 && (
        <div className="bg-black text-white rounded-lg p-6">
          <h2 className="text-lg font-bold mb-4">Flagged Pages</h2>
          
          <div className="space-y-4">
            {flaggedPages.map((page, idx) => (
              <div key={idx} className="bg-gray-900 p-4 rounded-lg">
                <div className="flex justify-between items-center">
                  <div>
                    <h3 className="font-medium">Page {page.pageNumber}</h3>
                    <p className="text-sm text-gray-400">
                      {(page.similarity * 100).toFixed(1)}% similar to page {page.matchedPage.pageNumber} in {page.matchedPage.filename}
                    </p>
                  </div>
                  <div>
                    <button 
                      onClick={() => setSelectedPage(idx)}
                      className="bg-blue-600 hover:bg-blue-700 text-white text-sm px-3 py-1 rounded transition-colors"
                    >
                      View Details
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Review History */}
      {reviewHistory && reviewHistory.length > 0 && (
        <div className="bg-black text-white rounded-lg p-6">
          <h2 className="text-lg font-bold mb-4">Review History</h2>
          
          <div className="space-y-2">
            {reviewHistory.map((entry, idx) => (
              <div key={idx} className="bg-gray-900 p-3 rounded-lg">
                <div className="flex justify-between items-center">
                  <div>
                    <span className={`inline-block text-xs px-2 py-1 rounded mr-2 ${getStatusColor(entry.status)}`}>
                      {entry.decision === 'keep' ? 'Kept' : 
                       entry.decision === 'archive' ? 'Archived' : 'Unsure'}
                    </span>
                    <span className="text-sm">by {entry.reviewer}</span>
                  </div>
                  <div className="text-xs text-gray-400">
                    {formatDate(entry.timestamp)}
                  </div>
                </div>
                {entry.notes && (
                  <p className="mt-2 text-sm text-gray-300 border-t border-gray-800 pt-2">
                    {entry.notes}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Notes and Actions */}
      <div className="bg-black text-white rounded-lg p-6">
        <h2 className="text-lg font-bold mb-4">Review Decision</h2>
        
        <div className="space-y-4">
          <div>
            <label htmlFor="notes" className="block text-sm font-medium text-gray-300 mb-2">
              Review Notes
            </label>
            <textarea
              id="notes"
              rows={4}
              className="w-full bg-gray-900 border border-gray-700 rounded-lg p-3 text-white focus:ring-blue-500 focus:border-blue-500"
              placeholder="Add notes about your decision..."
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            ></textarea>
          </div>
          
          <div className="flex justify-end space-x-4">
            <button
              onClick={() => handleDecision('unsure')}
              disabled={isProcessing}
              className="py-2 px-4 border border-gray-700 rounded-lg text-white hover:bg-gray-800 transition-colors"
            >
              Needs Further Review
            </button>
            <button
              onClick={() => handleDecision('archive')}
              disabled={isProcessing}
              className="py-2 px-4 bg-red-600 rounded-lg text-white hover:bg-red-700 transition-colors"
            >
              Archive as Duplicate
            </button>
            <button
              onClick={() => handleDecision('keep')}
              disabled={isProcessing}
              className="py-2 px-4 bg-green-600 rounded-lg text-white hover:bg-green-700 transition-colors"
            >
              Keep Document
            </button>
          </div>
        </div>
      </div>
      
      {/* Page Details Modal */}
      {selectedPage !== null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black bg-opacity-50">
          <div className="bg-gray-900 rounded-lg p-6 max-w-2xl w-full">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-bold text-white">
                Page Details
              </h3>
              <button
                onClick={() => setSelectedPage(null)}
                className="text-gray-400 hover:text-white"
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-gray-800 p-4 rounded-lg">
                <h4 className="font-medium text-white mb-2">
                  Page {flaggedPages[selectedPage].pageNumber}
                </h4>
                <p className="text-sm text-gray-300">
                  Page hash: {flaggedPages[selectedPage].pageHash.substring(0, 10)}...
                </p>
              </div>
              
              <div className="bg-gray-800 p-4 rounded-lg">
                <h4 className="font-medium text-white mb-2">
                  Similar Page {flaggedPages[selectedPage].matchedPage.pageNumber}
                </h4>
                <p className="text-sm text-gray-300">
                  Document: {flaggedPages[selectedPage].matchedPage.filename}
                </p>
              </div>
            </div>
            
            <div className="mt-4">
              <div className="flex justify-between items-center mb-2">
                <span className="text-gray-400">Similarity:</span>
                <span className="text-white font-medium">
                  {(flaggedPages[selectedPage].similarity * 100).toFixed(1)}%
                </span>
              </div>
              <div className="w-full bg-gray-700 rounded-full h-3">
                <div 
                  className={`h-3 rounded-full ${
                    flaggedPages[selectedPage].similarity > 0.8 ? 'bg-red-500' : 
                    flaggedPages[selectedPage].similarity > 0.5 ? 'bg-yellow-500' : 'bg-green-500'
                  }`}
                  style={{ width: `${(flaggedPages[selectedPage].similarity * 100).toFixed(0)}%` }}
                ></div>
              </div>
            </div>
            
            <div className="mt-6 flex justify-end">
              <button
                onClick={() => setSelectedPage(null)}
                className="py-2 px-4 bg-blue-600 rounded-lg text-white hover:bg-blue-700 transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Processing Overlay */}
      {isProcessing && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
          <div className="bg-gray-900 rounded-lg p-6">
            <div className="flex items-center">
              <div className="w-8 h-8 border-t-2 border-b-2 border-blue-500 rounded-full animate-spin mr-3"></div>
              <p className="text-white">Processing your decision...</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}