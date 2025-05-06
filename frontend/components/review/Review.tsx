'use client';

import React, { useState, useEffect } from 'react';
import { getAbsoluteApiUrl } from '../../services/baseApi';
import { ReviewData, WorkflowType, ReviewStatus, ReviewDecision, ReviewHistoryEntry, FlaggedPage } from '../../types/review';
import DirectImageDisplay from '../core/DirectImageDisplay';

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
  totalPages?: number;
  onDocumentAction: (documentId: string, decision: ReviewDecision, notes?: string) => void;
  onPageAction?: (pageIndex: number, decision: 'keep' | 'archive') => void;
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
  totalPages,
  onDocumentAction,
  onPageAction,
  onComplete
}: ReviewProps) {
  const [notes, setNotes] = useState("");
  const [selectedPage, setSelectedPage] = useState<number | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [uniquePages, setUniquePages] = useState<Array<{pageNumber: number, pageHash: string, status?: 'pending' | 'kept' | 'archived', imageUrl?: string}>>([]);
  
  // Log flaggedPages when component mounts or when they change
  useEffect(() => {
    if (flaggedPages && flaggedPages.length > 0) {
      console.log('Review component flaggedPages:', flaggedPages);
      console.log('Review component workflowType:', workflowType);
      
      // Check if imageUrl properties exist
      const hasImageUrls = flaggedPages.some(page => 'imageUrl' in page);
      console.log('FlaggedPages have imageUrl properties:', hasImageUrls);
      
      const hasMatchedImageUrls = flaggedPages.some(page => page.matchedPage && 'imageUrl' in page.matchedPage);
      console.log('MatchedPages have imageUrl properties:', hasMatchedImageUrls);
    }
  }, [flaggedPages, workflowType]);
  
  // Find unique pages - those not in the flagged pages list
  useEffect(() => {
    // Get document's total pages - either from flagged pages or props
    if (flaggedPages && flaggedPages.length > 0) {
      // If we have flagged pages, find pages that aren't flagged
      const flaggedPageNumbers = flaggedPages.map(page => page.pageNumber);
      // Get the total document pages either from props or infer from flagged pages
      const inferredTotalPages = Math.max(...flaggedPageNumbers);
      const documentTotalPages = totalPages || inferredTotalPages;
      
      // Find all page numbers that are in flaggedPages
      const flaggedPageNumbersSet = new Set(flaggedPageNumbers);
      
      // Create an array of pages that aren't in flaggedPages
      const nonFlaggedPages = [];
      for (let i = 1; i <= documentTotalPages; i++) {
        if (!flaggedPageNumbersSet.has(i)) {
          nonFlaggedPages.push({
            pageNumber: i,
            pageHash: `${docId}_page${i}`, // Simplified hash
            status: undefined
          });
        }
      }
      
      setUniquePages(nonFlaggedPages);
    } else {
      // If there are no flagged pages at all, we need to handle that case
      // For documents with no duplicates, show all pages as unique if totalPages is provided
      if (workflowType === 'intra-compare' && totalPages) {
        const allUniquePages = [];
        for (let i = 1; i <= totalPages; i++) {
          allUniquePages.push({
            pageNumber: i,
            pageHash: `${docId}_page${i}`,
            status: undefined
          });
        }
        
        setUniquePages(allUniquePages);
      } else {
        // No flagged pages and no totalPages prop means we don't know how many pages there are
        // Reset uniquePages to empty array
        setUniquePages([]);
      }
    }
  }, [flaggedPages, docId, workflowType, totalPages]);
  
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

  // Handle unique page action
  const handleUniquePageAction = (pageIndex: number, decision: 'keep' | 'archive') => {
    // Update the status in the local state
    setUniquePages(prev => {
      const updated = [...prev];
      updated[pageIndex] = {
        ...updated[pageIndex],
        status: decision === 'keep' ? 'kept' : 'archived'
      };
      return updated;
    });
    
    // If there's an onPageAction handler, call it with a special flag or mapping
    if (onPageAction) {
      // You might need to adapt this based on how your backend handles unique pages
      onPageAction(-1 - pageIndex, decision); // Using negative indices to indicate unique pages
    }
  };
  
  // Handle the keep action with auto-archive of matching page
  const handleKeepWithMatchArchive = (pageIndex: number) => {
    if (!onPageAction) return;
    
    const page = flaggedPages[pageIndex];
    
    // Find the matched page index
    const matchedPageIdx = flaggedPages.findIndex(p => 
      p.pageNumber === page.matchedPage.pageNumber && 
      p.matchedPage.pageNumber === page.pageNumber
    );
    
    // Keep the current page
    onPageAction(pageIndex, 'keep');
    
    // Archive the matched page if found
    if (matchedPageIdx !== -1) {
      onPageAction(matchedPageIdx, 'archive');
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
        
            <div>
          {/* Only include Duplicate Confidence - Medical score removed */}
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
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-lg font-bold">Flagged Pages</h2>
          </div>
          
          <div className="space-y-4">
            {flaggedPages.map((page, idx) => (
              <div key={idx} className="bg-gray-900 p-4 rounded-lg">
                <div className="flex justify-between items-center">
                  <div>
                    <h3 className="font-medium">Page {page.pageNumber}</h3>
                    <p className="text-sm text-gray-400">
                      {(page.similarity * 100).toFixed(1)}% similar to page {page.matchedPage.pageNumber} in {page.matchedPage.filename}
                    </p>
                    {page.status && (
                      <div className="mt-1">
                        <span className={`inline-block text-xs px-2 py-1 rounded ${
                          page.status === 'kept' ? 'bg-green-900/30 text-green-300' : 
                          page.status === 'archived' ? 'bg-red-900/30 text-red-300' : 
                          'bg-yellow-900/30 text-yellow-300'
                        }`}>
                          {page.status === 'kept' ? 'Kept' : 
                           page.status === 'archived' ? 'Archived' : 'Pending'}
                        </span>
                      </div>
                    )}
                  </div>
                  <div className="flex space-x-2">
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

      {/* Unique Pages */}
      {uniquePages && uniquePages.length > 0 ? (
        <div className="bg-black text-white rounded-lg p-6 mt-6">
          <h2 className="text-lg font-bold mb-4">Unique Pages</h2>
          <div className="flex flex-wrap">
            {uniquePages.map((page, idx) => (
              <div 
                key={idx} 
                className={`m-2 p-2 border rounded-lg cursor-pointer transition-colors ${
                  page.status === 'kept' ? 'border-green-500 bg-green-900 bg-opacity-20' :
                  page.status === 'archived' ? 'border-red-500 bg-red-900 bg-opacity-20' :
                  'border-gray-700 hover:border-blue-500'
                }`}
                onClick={() => setSelectedPage(-1 - idx)}
              >
                <div className="relative w-32 h-40 overflow-hidden bg-gray-800 rounded">
                  <div className="absolute inset-0 flex items-center justify-center text-gray-600">
                    {page.imageUrl ? (
                      <DirectImageDisplay 
                        pageNumber={page.pageNumber}
                        alt={`Page ${page.pageNumber}`}
                        className="w-full h-full object-contain"
                      />
                    ) : workflowType === 'intra-compare' ? (
                      <DirectImageDisplay 
                        pageNumber={page.pageNumber}
                        alt={`Page ${page.pageNumber}`}
                      />
                    ) : (
                      <div className="text-center text-gray-500">Page {page.pageNumber}</div>
                    )}
                  </div>
                </div>
                <div className="mt-2 text-center text-sm">
                  <div>Page {page.pageNumber}</div>
                  {page.status && (
                    <span className={`inline-block px-1.5 text-xs rounded ${
                      page.status === 'kept' ? 'bg-green-800 text-green-100' : 'bg-red-800 text-red-100'
                    }`}>
                      {page.status === 'kept' ? 'Kept' : 'Archived'}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : totalPages && uniquePages ? (
        <div className="bg-black text-white rounded-lg p-6 mt-6">
          <h2 className="text-lg font-bold mb-4">Unique Pages</h2>
          <div className="bg-gray-900 p-4 rounded-lg">
            <p className="text-sm text-yellow-400">
              No unique pages to display. To show unique pages for documents with no duplicates, 
              please provide the total page count through the totalPages prop.
            </p>
          </div>
        </div>
      ) : null}

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
          {workflowType === 'intra-compare' && (
            <div className="mb-4 p-4 bg-gray-900 rounded-lg">
              <h3 className="text-md font-medium mb-2">Page Decision Summary</h3>
              <div className="flex items-center space-x-4">
                <div>
                  <span className="text-sm text-gray-400">Kept: </span>
                  <span className="text-white font-medium">{flaggedPages.filter(p => p.status === 'kept').length}</span>
                </div>
                <div>
                  <span className="text-sm text-gray-400">Archived: </span>
                  <span className="text-white font-medium">{flaggedPages.filter(p => p.status === 'archived').length}</span>
                </div>
                <div>
                  <span className="text-sm text-gray-400">Pending: </span>
                  <span className="text-white font-medium">{flaggedPages.filter(p => !p.status || p.status === 'pending').length}</span>
                </div>
              </div>
              {flaggedPages.some(p => !p.status || p.status === 'pending') ? (
                <p className="mt-2 text-sm text-yellow-400">
                  Some pages still need review. Review each page by using the "Keep" or "Archive" buttons above.
                </p>
              ) : (
                <p className="mt-2 text-sm text-green-400">
                  All pages have been reviewed. You can complete the review process below.
                </p>
              )}
              
              {workflowType === 'intra-compare' && (
                <div className="mt-4 text-sm text-gray-300">
                  <p>For Intra-Document review:</p>
                  <ul className="list-disc pl-5 mt-1 space-y-1">
                    <li>Review each flagged page individually using the "Keep" or "Archive" buttons</li>
                    <li>You can see page details by clicking "View Details"</li>
                    <li>When finished, click "Complete Review" below to save your decisions</li>
                  </ul>
                </div>
              )}
            </div>
          )}
          
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
            {workflowType === 'intra-compare' ? (
              /* For intra-document workflow, show actions for completing the review */
              <>
                {flaggedPages.some(p => !p.status || p.status === 'pending') ? (
                  <button
                    className="py-2 px-4 bg-yellow-600 rounded-lg text-white hover:bg-yellow-700 transition-colors"
                    disabled={isProcessing}
                    onClick={() => {
                      if (window.confirm('Some pages have not been reviewed. Do you want to proceed anyway?')) {
                        handleDecision('keep');
                      }
                    }}
                  >
                    Complete Review (Pending Pages)
                  </button>
                ) : (
                  <button
                    className="py-2 px-4 bg-green-600 rounded-lg text-white hover:bg-green-700 transition-colors"
                    disabled={isProcessing}
                    onClick={() => handleDecision('keep')}
                  >
                    Complete Review
                  </button>
                )}
              </>
            ) : (
              /* For other workflows, show the original document-level decision buttons */
              <>
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
              </>
            )}
          </div>
        </div>
      </div>
      
      {/* Page Details Modal */}
      {selectedPage !== null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black bg-opacity-50">
          <div className="bg-gray-900 rounded-lg p-6 w-4/5 max-h-[90vh] overflow-y-auto">
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
            
            {selectedPage >= 0 ? (
              // Flagged page view (with comparison)
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-gray-800 rounded-lg overflow-hidden">
                  <h4 className="font-medium text-white p-2 border-b border-gray-700">
                    Page {flaggedPages[selectedPage].pageNumber}
                  </h4>
                  <div className="p-4">
                    <div className="border border-gray-700 rounded mb-3 overflow-hidden">
                      <div id="page1-image-container" className="min-h-[200px] flex items-center justify-center">
                        {(flaggedPages[selectedPage] as any).imageUrl ? (
                          <DirectImageDisplay 
                            pageNumber={flaggedPages[selectedPage].pageNumber}
                            alt={`Page ${flaggedPages[selectedPage].pageNumber}`}
                            className="w-full h-auto"
                          />
                        ) : workflowType === 'compare' ? (
                          <DirectImageDisplay 
                            pageNumber={flaggedPages[selectedPage].pageNumber}
                            alt={`Page ${flaggedPages[selectedPage].pageNumber}`}
                            className="w-full h-auto"
                          />
                        ) : workflowType === 'intra-compare' ? (
                          <DirectImageDisplay 
                            pageNumber={flaggedPages[selectedPage].pageNumber}
                            alt={`Page ${flaggedPages[selectedPage].pageNumber}`}
                          />
                        ) : (
                          <DirectImageDisplay 
                            pageNumber={flaggedPages[selectedPage].pageNumber}
                            alt={`Page ${flaggedPages[selectedPage].pageNumber}`}
                            className="w-full h-auto"
                          />
                        )}
                      </div>
                    </div>
                    <p className="text-sm text-gray-300">
                      Hash: {flaggedPages[selectedPage].pageHash.substring(0, 10)}...
                    </p>
                    
                    {/* Add Keep button under this page */}
                    {workflowType === 'intra-compare' && onPageAction && !flaggedPages[selectedPage].status && (
                      <div className="mt-4">
                        <button 
                          onClick={() => {
                            if (window.confirm(`Are you sure you want to keep page ${flaggedPages[selectedPage].pageNumber} and archive page ${flaggedPages[selectedPage].matchedPage.pageNumber}?`)) {
                              // Find the matched page index
                              const matchedPageIdx = flaggedPages.findIndex(p => 
                                p.pageNumber === flaggedPages[selectedPage].matchedPage.pageNumber && 
                                p.matchedPage.pageNumber === flaggedPages[selectedPage].pageNumber
                              );
                              
                              // Keep this page and archive the matched page
                              onPageAction(selectedPage, 'keep');
                              if (matchedPageIdx !== -1) {
                                onPageAction(matchedPageIdx, 'archive');
                              }
                              setSelectedPage(null);
                            }
                          }}
                          className="w-full py-2 px-4 bg-green-600 rounded-lg text-white hover:bg-green-700 transition-colors"
                        >
                          Keep This Page
                        </button>
                      </div>
                    )}
                  </div>
                </div>
                
                <div className="bg-gray-800 rounded-lg overflow-hidden">
                  <h4 className="font-medium text-white p-2 border-b border-gray-700">
                    Similar Page {flaggedPages[selectedPage].matchedPage.pageNumber}
                  </h4>
                  <div className="p-4">
                    <div className="border border-gray-700 rounded mb-3 overflow-hidden">
                      <div id="page2-image-container" className="min-h-[200px] flex items-center justify-center">
                        {(flaggedPages[selectedPage].matchedPage as any).imageUrl ? (
                          <DirectImageDisplay 
                            pageNumber={flaggedPages[selectedPage].matchedPage.pageNumber}
                            alt={`Page ${flaggedPages[selectedPage].matchedPage.pageNumber}`}
                            className="w-full h-auto"
                          />
                        ) : workflowType === 'compare' ? (
                          <DirectImageDisplay 
                            pageNumber={flaggedPages[selectedPage].matchedPage.pageNumber}
                            alt={`Page ${flaggedPages[selectedPage].matchedPage.pageNumber}`}
                            className="w-full h-auto"
                          />
                        ) : workflowType === 'intra-compare' ? (
                          <DirectImageDisplay 
                            pageNumber={flaggedPages[selectedPage].matchedPage.pageNumber}
                            alt={`Page ${flaggedPages[selectedPage].matchedPage.pageNumber}`}
                          />
                        ) : (
                          <DirectImageDisplay 
                            pageNumber={flaggedPages[selectedPage].matchedPage.pageNumber}
                            alt={`Page ${flaggedPages[selectedPage].matchedPage.pageNumber}`}
                            className="w-full h-auto"
                          />
                        )}
                      </div>
                    </div>
                    <p className="text-sm text-gray-300">
                      Document: {flaggedPages[selectedPage].matchedPage.filename}
                    </p>
                    
                    {/* Add Keep button under this page */}
                    {workflowType === 'intra-compare' && onPageAction && !flaggedPages[selectedPage].status && (
                      <div className="mt-4">
                        <button 
                          onClick={() => {
                            if (window.confirm(`Are you sure you want to keep page ${flaggedPages[selectedPage].matchedPage.pageNumber} and archive page ${flaggedPages[selectedPage].pageNumber}?`)) {
                              // Find the matched page index
                              const matchedPageIdx = flaggedPages.findIndex(p => 
                                p.pageNumber === flaggedPages[selectedPage].matchedPage.pageNumber && 
                                p.matchedPage.pageNumber === flaggedPages[selectedPage].pageNumber
                              );
                              
                              // Archive this page and keep the matched page
                              onPageAction(selectedPage, 'archive');
                              if (matchedPageIdx !== -1) {
                                onPageAction(matchedPageIdx, 'keep');
                              }
                              setSelectedPage(null);
                            }
                          }}
                          className="w-full py-2 px-4 bg-green-600 rounded-lg text-white hover:bg-green-700 transition-colors"
                        >
                          Keep This Page
                        </button>
                      </div>
                    )}
                  </div>
                </div>
                
                <div className="col-span-2 mt-4">
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
              </div>
            ) : (
              // Unique page view (single page)
              <div className="bg-gray-800 rounded-lg overflow-hidden">
                {selectedPage < 0 && (
                  <>
                    <h4 className="font-medium text-white p-2 border-b border-gray-700">
                      Page {uniquePages[-1 - selectedPage].pageNumber} (Unique)
                    </h4>
                    <div className="p-4">
                      <div className="border border-gray-700 rounded mb-3 overflow-hidden">
                        <div id="unique-page-image-container" className="min-h-[400px] flex items-center justify-center">
                          {workflowType === 'intra-compare' ? (
                            <DirectImageDisplay 
                              pageNumber={uniquePages[-1 - selectedPage].pageNumber}
                              alt={`Page ${uniquePages[-1 - selectedPage].pageNumber}`}
                            />
                          ) : (
                            <DirectImageDisplay 
                              pageNumber={uniquePages[-1 - selectedPage].pageNumber}
                              alt={`Page ${uniquePages[-1 - selectedPage].pageNumber}`}
                              className="w-full h-auto"
                            />
                          )}
                        </div>
                      </div>
                      <p className="text-sm text-gray-300">
                        This page appears to be unique in this document
                      </p>
                    </div>
                  </>
                )}
              </div>
            )}
            
            <div className="mt-6 flex justify-end space-x-2">
              {/* Actions for flagged pages - Keep Both and Archive Both */}
              {selectedPage >= 0 && workflowType === 'intra-compare' && onPageAction && !flaggedPages[selectedPage].status && (
                <>
                  <button 
                    onClick={() => {
                      if (window.confirm('Are you sure you want to archive both pages?')) {
                        // Find the matched page index
                        const matchedPageIdx = flaggedPages.findIndex(p => 
                          p.pageNumber === flaggedPages[selectedPage].matchedPage.pageNumber && 
                          p.matchedPage.pageNumber === flaggedPages[selectedPage].pageNumber
                        );
                        
                        // Archive both pages
                        onPageAction(selectedPage, 'archive');
                        if (matchedPageIdx !== -1) {
                          onPageAction(matchedPageIdx, 'archive');
                        }
                        setSelectedPage(null);
                      }
                    }}
                    className="py-2 px-4 bg-red-600 rounded-lg text-white hover:bg-red-700 transition-colors"
                  >
                    Archive Both
                  </button>
                  <button 
                    onClick={() => {
                      if (window.confirm('Are you sure you want to keep both pages?')) {
                        // Find the matched page index
                        const matchedPageIdx = flaggedPages.findIndex(p => 
                          p.pageNumber === flaggedPages[selectedPage].matchedPage.pageNumber && 
                          p.matchedPage.pageNumber === flaggedPages[selectedPage].pageNumber
                        );
                        
                        // Keep both pages
                        onPageAction(selectedPage, 'keep');
                        if (matchedPageIdx !== -1) {
                          onPageAction(matchedPageIdx, 'keep');
                        }
                        setSelectedPage(null);
                      }
                    }}
                    className="py-2 px-4 bg-green-600 rounded-lg text-white hover:bg-green-700 transition-colors"
                  >
                    Keep Both
                  </button>
                </>
              )}
              
              {/* Actions for unique pages */}
              {selectedPage < 0 && workflowType === 'intra-compare' && !uniquePages[-1 - selectedPage].status && (
                <>
                  <button 
                    onClick={() => {
                      if (window.confirm(`Are you sure you want to archive page ${uniquePages[-1 - selectedPage].pageNumber}?`)) {
                        handleUniquePageAction(-1 - selectedPage, 'archive');
                      setSelectedPage(null);
                      }
                    }}
                    className="py-2 px-4 bg-red-600 rounded-lg text-white hover:bg-red-700 transition-colors"
                  >
                    Archive Page
                  </button>
                  <button 
                    onClick={() => {
                      if (window.confirm(`Are you sure you want to keep page ${uniquePages[-1 - selectedPage].pageNumber}?`)) {
                        handleUniquePageAction(-1 - selectedPage, 'keep');
                      setSelectedPage(null);
                      }
                    }}
                    className="py-2 px-4 bg-green-600 rounded-lg text-white hover:bg-green-700 transition-colors"
                  >
                    Keep Page
                  </button>
                </>
              )}
              
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