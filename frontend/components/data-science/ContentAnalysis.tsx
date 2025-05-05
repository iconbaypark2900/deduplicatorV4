'use client';

import React, { useState } from 'react';
import UploadDropzone from '../core/UploadDropzone';
import { dataScienceService } from '../../services/dataScienceService';
import { ContentAnalysisResult, TopicModel, MedicalEntityCount, SectionData } from '../../types/document';
import { ReviewData } from '../../types/review';

interface Props {
  onComplete?: (data: ReviewData) => void;
}

/**
 * Content Analysis component for analyzing document content patterns.
 * Extracts topics, entities, and document structure.
 */
export default function ContentAnalysis({ onComplete }: Props) {
  const [result, setResult] = useState<ContentAnalysisResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'topics' | 'entities' | 'sections'>('topics');
  const [reportUrl, setReportUrl] = useState<string | null>(null);

  // Handle file upload and content analysis
  const handleUpload = async (files: File | File[]) => {
    const docs = Array.isArray(files) ? files : [files];

    setIsLoading(true);
    setError(null);
    
    try {
      const analysisResult = await dataScienceService.analyzeContent(docs);
      setResult(analysisResult);
      
      if (analysisResult.report_url) {
        setReportUrl(analysisResult.report_url);
      }
      
      // If onComplete callback is provided, format data for review
      if (onComplete) {
        onComplete({
          documentId: analysisResult.document_id || `content-analysis-${Date.now()}`,
          filename: analysisResult.filename || `Content Analysis (${analysisResult.total_documents} documents)`,
          workflowType: 'content',
          flaggedPages: [],  // No duplicate flagging in content analysis
          status: 'pending',
          reviewHistory: [],
          medicalConfidence: analysisResult.medical_terms.length > 0 ? 0.8 : 0.2,
          duplicateConfidence: 0  // Not relevant for content analysis
        });
      }
    } catch (error) {
      console.error('Content analysis failed:', error);
      setError('Failed to analyze content. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  // Function to create word clouds - this is a simplified version
  // A real implementation would use a proper word cloud library
  const renderWordCloud = (words: MedicalEntityCount[], maxCount: number) => {
    return (
      <div className="flex flex-wrap gap-2 justify-center p-4">
        {words.map((word, index) => {
          const size = Math.max(1, Math.min(5, Math.floor(word.count / maxCount * 5)));
          const sizeClasses = [
            'text-sm',
            'text-base',
            'text-lg',
            'text-xl',
            'text-2xl'
          ];
          
          return (
            <span 
              key={index}
              className={`inline-block px-2 py-1 bg-gray-800 text-blue-300 rounded ${sizeClasses[size - 1]}`}
              style={{ opacity: 0.5 + word.count / maxCount * 0.5 }}
            >
              {word.term}
            </span>
          );
        })}
      </div>
    );
  };

  // Render the Topics tab content
  const renderTopics = () => {
    if (!result) return null;
    
    return (
      <div className="space-y-6">
        <h3 className="text-lg font-semibold text-white">Document Topics</h3>
        
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {result.topics.map(topic => (
            <div key={topic.topic_id} className="bg-gray-900 rounded-lg p-4 border border-gray-700">
              <div className="flex justify-between items-center mb-3">
                <h4 className="font-medium">Topic {topic.topic_id + 1}</h4>
                <span className="bg-blue-600 text-white text-xs px-2 py-1 rounded">
                  {(topic.weight * 100).toFixed(1)}%
                </span>
              </div>
              
              <div className="flex flex-wrap gap-1">
                {topic.words.map((word, idx) => (
                  <span key={idx} className="inline-block px-2 py-1 bg-gray-800 text-blue-200 text-xs rounded">
                    {word}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  };

  // Render the Entities tab content
  const renderEntities = () => {
    if (!result) return null;
    
    // Find maximum count for scaling
    const allEntities = [
      ...result.medical_terms,
      ...result.medications,
      ...result.conditions,
      ...result.procedures
    ];
    
    const maxCount = Math.max(...allEntities.map(e => e.count), 1);
    
    return (
      <div className="space-y-8">
        {/* Medical Terms */}
        <div>
          <h3 className="text-lg font-semibold text-white mb-2">Medical Terms</h3>
          {result.medical_terms.length > 0 ? (
            renderWordCloud(result.medical_terms, maxCount)
          ) : (
            <p className="text-gray-400 text-center py-4">No medical terms detected</p>
          )}
        </div>
        
        {/* Medications */}
        <div>
          <h3 className="text-lg font-semibold text-white mb-2">Medications</h3>
          {result.medications.length > 0 ? (
            renderWordCloud(result.medications, maxCount)
          ) : (
            <p className="text-gray-400 text-center py-4">No medications detected</p>
          )}
        </div>
        
        {/* Medical Conditions */}
        <div>
          <h3 className="text-lg font-semibold text-white mb-2">Medical Conditions</h3>
          {result.conditions.length > 0 ? (
            renderWordCloud(result.conditions, maxCount)
          ) : (
            <p className="text-gray-400 text-center py-4">No medical conditions detected</p>
          )}
        </div>
      </div>
    );
  };

  // Render the Sections tab content
  const renderSections = () => {
    if (!result) return null;
    
    return (
      <div className="space-y-6">
        <h3 className="text-lg font-semibold text-white">Document Sections</h3>
        
        <div className="bg-gray-900 rounded-lg p-4 border border-gray-700">
          <table className="min-w-full divide-y divide-gray-700">
            <thead>
              <tr>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                  Section Name
                </th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                  Frequency
                </th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                  Percentage
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-700">
              {result.sections.map((section, idx) => (
                <tr key={idx} className={idx % 2 === 0 ? 'bg-gray-800' : 'bg-gray-900'}>
                  <td className="px-4 py-2 whitespace-nowrap text-sm text-white">
                    {section.name}
                  </td>
                  <td className="px-4 py-2 whitespace-nowrap text-sm text-gray-300">
                    {section.count}
                  </td>
                  <td className="px-4 py-2 whitespace-nowrap">
                    <div className="w-full bg-gray-700 rounded-full h-2">
                      <div
                        className="bg-blue-500 h-2 rounded-full"
                        style={{ 
                          width: `${(section.count / result.total_documents * 100).toFixed(1)}%` 
                        }}
                      ></div>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-6">
      <div className="bg-black text-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold mb-4">Content Analysis</h3>
        <p className="text-gray-300 mb-4">
          Upload documents to analyze content patterns, extract topics, and identify medical terminology.
        </p>
        <UploadDropzone 
          onUpload={handleUpload} 
          mode="multiple"
          label="Upload documents for content analysis"
          sublabel="Select multiple PDF files (max 50MB each)"
        />
      </div>

      {isLoading && (
        <div className="flex justify-center items-center py-8">
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
          <span className="ml-3 text-gray-600 dark:text-gray-400">Analyzing document content...</span>
        </div>
      )}

      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded dark:bg-red-900/30 dark:text-red-300 dark:border-red-800">
          <p>{error}</p>
        </div>
      )}

      {result && (
        <div className="space-y-6">
          {/* Analysis Summary */}
          <div className="bg-black text-white rounded-lg shadow p-6">
            <h3 className="text-xl font-bold mb-4">Content Analysis Summary</h3>
            
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
              <div className="border border-gray-700 rounded-lg p-4 bg-gray-900">
                <h4 className="text-gray-400 text-sm">Documents</h4>
                <p className="text-2xl font-bold">{result.total_documents}</p>
              </div>
              
              <div className="border border-gray-700 rounded-lg p-4 bg-gray-900">
                <h4 className="text-gray-400 text-sm">Topics</h4>
                <p className="text-2xl font-bold">{result.topics.length}</p>
              </div>
              
              <div className="border border-gray-700 rounded-lg p-4 bg-gray-900">
                <h4 className="text-gray-400 text-sm">Avg Length</h4>
                <p className="text-2xl font-bold">{Math.round(result.average_word_count)} words</p>
              </div>
              
              <div className="border border-gray-700 rounded-lg p-4 bg-gray-900">
                <h4 className="text-gray-400 text-sm">Medical Terms</h4>
                <p className="text-2xl font-bold">{result.medical_terms.length}</p>
              </div>
            </div>
            
            {/* Detailed Report Link */}
            {reportUrl && (
              <div className="mt-6 flex justify-center">
                <a 
                  href={reportUrl} 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded inline-flex items-center transition-colors"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  View Full Report
                </a>
              </div>
            )}
          </div>
          
          {/* Tabs for different analysis views */}
          <div className="bg-black text-white rounded-lg shadow p-6">
            <div className="border-b border-gray-700 mb-6">
              <nav className="-mb-px flex space-x-8">
                <button
                  onClick={() => setActiveTab('topics')}
                  className={`${
                    activeTab === 'topics'
                      ? 'border-blue-500 text-blue-500'
                      : 'border-transparent text-gray-400 hover:text-gray-300 hover:border-gray-300'
                  } whitespace-nowrap py-4 px-1 border-b-2 font-medium transition-colors`}
                >
                  Topics
                </button>
                <button
                  onClick={() => setActiveTab('entities')}
                  className={`${
                    activeTab === 'entities'
                      ? 'border-blue-500 text-blue-500'
                      : 'border-transparent text-gray-400 hover:text-gray-300 hover:border-gray-300'
                  } whitespace-nowrap py-4 px-1 border-b-2 font-medium transition-colors`}
                >
                  Medical Entities
                </button>
                <button
                  onClick={() => setActiveTab('sections')}
                  className={`${
                    activeTab === 'sections'
                      ? 'border-blue-500 text-blue-500'
                      : 'border-transparent text-gray-400 hover:text-gray-300 hover:border-gray-300'
                  } whitespace-nowrap py-4 px-1 border-b-2 font-medium transition-colors`}
                >
                  Document Sections
                </button>
              </nav>
            </div>
            
            {/* Tab content */}
            <div>
              {activeTab === 'topics' && renderTopics()}
              {activeTab === 'entities' && renderEntities()}
              {activeTab === 'sections' && renderSections()}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}