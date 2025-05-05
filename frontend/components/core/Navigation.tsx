'use client';

import React, { useState } from 'react';
import { ReviewData, ReviewHistoryEntry, WorkflowType } from '../../types/review';

// Import analysis components
import DocumentComparison from '../analysis/DocumentComparison';
import SingleDocument from '../analysis/SingleDocument';
import BatchFolder from '../analysis/BatchFolder';

// Import data science components
import MedicalAnalysis from '../data-science/MedicalAnalysis';
import DocumentClustering from '../data-science/DocumentClustering';
import ContentAnalysis from '../data-science/ContentAnalysis';

// Import review component
import Review from '../review/Review';

// Tab button component for consistent styling
const TabButton = ({ 
  label, 
  active, 
  onClick 
}: { 
  label: string; 
  active: boolean; 
  onClick: () => void; 
}) => (
  <button
    onClick={onClick}
    className={`${
      active
        ? 'border-blue-500 text-blue-600 dark:text-blue-400'
        : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-300'
    } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm transition-colors`}
  >
    {label}
  </button>
);

export default function Navigation() {
  // State for tracking the active tab
  const [activeTab, setActiveTab] = useState<WorkflowType>('compare');
  
  // State for tracking document being reviewed
  const [reviewData, setReviewData] = useState<ReviewData | null>(null);
  
  // Settings for analysis
  const [settings, setSettings] = useState({
    chunkType: 'page',
    similarityThreshold: 80
  });

  // Handler for when an analysis completes and needs review
  const handleWorkflowComplete = (data: ReviewData) => {
    setReviewData({
      ...data,
      status: 'pending',
      reviewHistory: data.reviewHistory || [],
      lastReviewer: data.lastReviewer,
      lastReviewedAt: data.lastReviewedAt
    });
    setActiveTab('compare');
    // Show review tab
    setTimeout(() => {
      document.getElementById('review-tab')?.scrollIntoView({ behavior: 'smooth' });
    }, 100);
  };

  // Handler for document actions in review
  const handleDocumentAction = async (documentId: string, decision: 'keep' | 'archive' | 'unsure', notes?: string) => {
    try {
      // API call would go here
      console.log(`Document ${documentId} action: ${decision}`, notes);

      // Update review data state
      setReviewData(prevData => {
        if (!prevData) return prevData;
        
        const newEntry: ReviewHistoryEntry = {
          status: decision === 'keep' ? 'reviewed' : 'archived',
          decision: decision,
          reviewer: 'current_user',
          timestamp: new Date().toISOString(),
          notes: notes
        };
        
        return {
          ...prevData,
          status: decision === 'keep' ? 'reviewed' : 'archived',
          reviewHistory: [...prevData.reviewHistory, newEntry],
          lastReviewer: 'current_user',
          lastReviewedAt: new Date().toISOString()
        };
      });

      // Show success notification
      alert(`Document ${decision === 'keep' ? 'kept' : 'archived'} successfully`);
    } catch (error) {
      console.error('Failed to update document status:', error);
      alert('Failed to update document status');
    }
  };

  // Handler for when review is completed
  const handleReviewComplete = () => {
    setReviewData(null);
    setActiveTab('compare');
  };

  return (
    <div className="space-y-6">
      {/* Tab Navigation */}
      <div className="border-b border-gray-200 dark:border-gray-800">
        <nav className="flex flex-wrap space-x-2 md:space-x-8" aria-label="Tabs">
          <TabButton
            label="Document Comparison"
            active={activeTab === 'compare'}
            onClick={() => setActiveTab('compare')}
          />
          <TabButton
            label="Single Document"
            active={activeTab === 'single'}
            onClick={() => setActiveTab('single')}
          />
          <TabButton
            label="Batch Folder"
            active={activeTab === 'batch'}
            onClick={() => setActiveTab('batch')}
          />
          <TabButton
            label="Medical Analysis"
            active={activeTab === 'medical'}
            onClick={() => setActiveTab('medical')}
          />
          <TabButton
            label="Document Clusters"
            active={activeTab === 'cluster'}
            onClick={() => setActiveTab('cluster')}
          />
          <TabButton
            label="Content Analysis"
            active={activeTab === 'content'}
            onClick={() => setActiveTab('content')}
          />
          {reviewData && (
            <TabButton
              label="Review Results"
              active={activeTab === 'review'}
              onClick={() => setActiveTab('review')}
            />
          )}
        </nav>
      </div>

      {/* Content based on active tab */}
      <div className="mt-6">
        {activeTab === 'compare' && (
          <DocumentComparison 
            onComplete={handleWorkflowComplete} 
          />
        )}
        {activeTab === 'single' && (
          <SingleDocument 
            settings={settings} 
            onComplete={handleWorkflowComplete} 
          />
        )}
        {activeTab === 'batch' && (
          <BatchFolder 
            settings={settings} 
            onComplete={handleWorkflowComplete} 
          />
        )}
        {activeTab === 'medical' && (
          <MedicalAnalysis 
            onComplete={handleWorkflowComplete} 
          />
        )}
        {activeTab === 'cluster' && (
          <DocumentClustering 
            onComplete={handleWorkflowComplete} 
          />
        )}
        {activeTab === 'content' && (
          <ContentAnalysis 
            onComplete={handleWorkflowComplete} 
          />
        )}
        {activeTab === 'review' && reviewData && (
          <Review
            docId={reviewData.documentId}
            filename={reviewData.filename}
            workflowType={reviewData.workflowType}
            flaggedPages={reviewData.flaggedPages}
            medicalConfidence={reviewData.medicalConfidence || 0}
            duplicateConfidence={reviewData.duplicateConfidence || 0}
            status={reviewData.status}
            reviewHistory={reviewData.reviewHistory}
            lastReviewer={reviewData.lastReviewer}
            lastReviewedAt={reviewData.lastReviewedAt}
            onDocumentAction={handleDocumentAction}
            onComplete={handleReviewComplete}
          />
        )}
      </div>

      {/* Review panel - shown if review data exists */}
      {reviewData && (
        <div id="review-tab" className="mt-8 pt-4 border-t border-gray-200 dark:border-gray-800">
          <h2 className="text-xl font-bold mb-4 dark:text-white">Review Results</h2>
          <Review
            docId={reviewData.documentId}
            filename={reviewData.filename}
            workflowType={reviewData.workflowType}
            flaggedPages={reviewData.flaggedPages}
            medicalConfidence={reviewData.medicalConfidence || 0}
            duplicateConfidence={reviewData.duplicateConfidence || 0}
            status={reviewData.status}
            reviewHistory={reviewData.reviewHistory}
            lastReviewer={reviewData.lastReviewer}
            lastReviewedAt={reviewData.lastReviewedAt}
            onDocumentAction={handleDocumentAction}
            onComplete={handleReviewComplete}
          />
        </div>
      )}
    </div>
  );
}