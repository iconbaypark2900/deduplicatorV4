'use client';

import React, { useState } from 'react';
import BatchFolder from '../analysis/BatchFolder';
import IntraDocumentComparison from '../analysis/IntraDocumentComparison';
import type { ReviewData } from '../../types/review';

interface Props {
  onComplete?: (data: ReviewData) => void;
}

/**
 * ClientAnalysis component provides both batch folder comparison and
 * intra-document analysis workflows in a single UI. Users can switch
 * between the two modes using local tabs. Results are passed to the
 * provided onComplete callback when analysis finishes.
 */
export default function ClientAnalysis({ onComplete }: Props) {
  const [activeTab, setActiveTab] = useState<'batch' | 'intra'>('batch');

  const tabClass = (tab: 'batch' | 'intra') =>
    `px-3 py-2 border-b-2 text-sm font-medium cursor-pointer ` +
    (activeTab === tab
      ? 'border-blue-500 text-blue-600'
      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300');

  return (
    <div className="space-y-6">
      <div className="border-b border-gray-200">
        <nav className="flex space-x-2" aria-label="Client analysis tabs">
          <button className={tabClass('batch')} onClick={() => setActiveTab('batch')}>
            Batch Folder
          </button>
          <button className={tabClass('intra')} onClick={() => setActiveTab('intra')}>
            Intra Document
          </button>
        </nav>
      </div>

      {activeTab === 'batch' && (
        <BatchFolder
          settings={{ chunkType: 'page', similarityThreshold: 80 }}
          onComplete={onComplete}
        />
      )}

      {activeTab === 'intra' && <IntraDocumentComparison onComplete={onComplete} />}
    </div>
  );
}
