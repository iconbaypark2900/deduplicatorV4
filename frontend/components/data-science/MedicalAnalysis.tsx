'use client';

import React, { useState } from 'react';
import UploadDropzone from '../core/UploadDropzone';
import { dataScienceService } from '../../services/dataScienceService';
import { MedicalAnalysisResult, MedicalPageAnalysis } from '../../types/document';
import { ReviewData } from '../../types/review';

interface Props {
  onComplete?: (data: ReviewData) => void;
}

/**
 * Medical Analysis component for detecting and analyzing medical content in documents.
 * Uses the backend data science module for analysis.
 */
export default function MedicalAnalysis({ onComplete }: Props) {
  const [result, setResult] = useState<MedicalAnalysisResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Handle file upload and medical analysis
  const handleUpload = async (file: File) => {
    setIsLoading(true);
    setError(null);
    
    try {
      const analysisResult = await dataScienceService.analyzeMedicalContent(file);
      setResult(analysisResult);
      
      // If onComplete callback is provided, format data for review
      if (onComplete) {
        onComplete({
          documentId: analysisResult.document_id,
          filename: analysisResult.filename,
          workflowType: 'medical',
          flaggedPages: [],  // No duplicate flagging in medical analysis
          status: 'pending',
          reviewHistory: [],
          medicalConfidence: analysisResult.confidence,
          duplicateConfidence: 0  // Not relevant for medical analysis
        });
      }
    } catch (error) {
      console.error('Medical analysis failed:', error);
      setError('Failed to analyze medical content. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  // Helper function to get appropriate color based on confidence
  const getConfidenceColor = (confidence: number): string => {
    if (confidence > 0.8) return 'bg-green-500 dark:bg-green-600';
    if (confidence > 0.5) return 'bg-yellow-500 dark:bg-yellow-600';
    return 'bg-red-500 dark:bg-red-600';
  };

  // Helper function to get specialty badge color
  const getSpecialtyBadgeColor = (specialty: string): string => {
    const specialtyColors: {[key: string]: string} = {
      'cardiology': 'bg-red-100 text-red-800 border-red-300 dark:bg-red-900/30 dark:text-red-300 dark:border-red-800',
      'neurology': 'bg-purple-100 text-purple-800 border-purple-300 dark:bg-purple-900/30 dark:text-purple-300 dark:border-purple-800',
      'oncology': 'bg-yellow-100 text-yellow-800 border-yellow-300 dark:bg-yellow-900/30 dark:text-yellow-300 dark:border-yellow-800',
      'orthopedics': 'bg-blue-100 text-blue-800 border-blue-300 dark:bg-blue-900/30 dark:text-blue-300 dark:border-blue-800',
      'pediatrics': 'bg-green-100 text-green-800 border-green-300 dark:bg-green-900/30 dark:text-green-300 dark:border-green-800',
      'radiology': 'bg-gray-100 text-gray-800 border-gray-300 dark:bg-gray-800 dark:text-gray-300 dark:border-gray-700',
      'gastroenterology': 'bg-orange-100 text-orange-800 border-orange-300 dark:bg-orange-900/30 dark:text-orange-300 dark:border-orange-800'
    };
    
    return specialtyColors[specialty.toLowerCase()] || 'bg-gray-100 text-gray-800 border-gray-300 dark:bg-gray-800 dark:text-gray-300 dark:border-gray-700';
  };

  return (
    <div className="space-y-6">
      <div className="bg-black text-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold mb-4">Medical Content Analysis</h3>
        <p className="text-gray-300 mb-4">
          Upload a document to analyze for medical content, detect specialties, and extract medical terms.
        </p>
        <UploadDropzone 
          onUpload={handleUpload} 
          mode="single"
          label="Upload document for medical analysis"
          sublabel="PDF files only (max 50MB)"
        />
      </div>

      {isLoading && (
        <div className="flex justify-center items-center py-8">
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
          <span className="ml-3 text-gray-600 dark:text-gray-400">Analyzing medical content...</span>
        </div>
      )}

      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded dark:bg-red-900/30 dark:text-red-300 dark:border-red-800">
          <p>{error}</p>
        </div>
      )}

      {result && (
        <div className="space-y-6">
          {/* Document Summary */}
          <div className="bg-black text-white rounded-lg shadow p-6">
            <h3 className="text-xl font-bold mb-4">Document Summary</h3>
            
            <div className="flex items-center mb-6">
              <div className={`h-16 w-16 rounded-full flex items-center justify-center ${result.is_medical ? 'bg-green-500' : 'bg-red-500'} text-white text-2xl font-bold mr-4`}>
                {result.is_medical ? '✓' : '✗'}
              </div>
              
              <div>
                <h4 className="text-lg font-semibold">
                  {result.is_medical 
                    ? 'Medical Document Detected' 
                    : 'Non-Medical Document'
                  }
                </h4>
                <p className="text-gray-300">
                  Confidence: {(result.confidence * 100).toFixed(1)}%
                </p>
              </div>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Medical Confidence */}
              <div className="bg-gray-900 rounded-lg p-4">
                <h4 className="text-gray-300 mb-2">Medical Confidence</h4>
                <div className="w-full bg-gray-700 rounded-full h-4 mb-2">
                  <div 
                    className={`h-4 rounded-full ${getConfidenceColor(result.confidence)}`}
                    style={{ width: `${(result.confidence * 100).toFixed(1)}%` }}
                  ></div>
                </div>
                <div className="text-right text-white font-semibold">
                  {(result.confidence * 100).toFixed(1)}%
                </div>
              </div>
              
              {/* Medical Content Ratio */}
              <div className="bg-gray-900 rounded-lg p-4">
                <h4 className="text-gray-300 mb-2">Medical Pages Ratio</h4>
                <div className="w-full bg-gray-700 rounded-full h-4 mb-2">
                  <div 
                    className="h-4 rounded-full bg-blue-500"
                    style={{ width: `${(result.medical_page_ratio * 100).toFixed(1)}%` }}
                  ></div>
                </div>
                <div className="text-right text-white font-semibold">
                  {(result.medical_page_ratio * 100).toFixed(1)}% of pages
                </div>
              </div>
            </div>
            
            {/* Specialty */}
            {result.specialty && (
              <div className="mt-6">
                <h4 className="text-gray-300 mb-2">Detected Specialty</h4>
                <span className={`inline-block px-3 py-1 rounded-full border ${getSpecialtyBadgeColor(result.specialty)} text-sm font-semibold`}>
                  {result.specialty}
                </span>
              </div>
            )}
          </div>
          
          {/* Page Analysis */}
          <div className="bg-black text-white rounded-lg shadow p-6">
            <h3 className="text-xl font-bold mb-4">Page-by-Page Analysis</h3>
            
            <div className="space-y-4">
              {result.pages.map((page: MedicalPageAnalysis) => (
                <div key={page.page_num} className="border border-gray-700 rounded-lg p-4">
                  <div className="flex justify-between items-center mb-3">
                    <h4 className="font-semibold">Page {page.page_num}</h4>
                    
                    <div className="flex items-center">
                      <span className={`inline-block w-3 h-3 rounded-full ${page.is_medical ? 'bg-green-500' : 'bg-red-500'} mr-2`}></span>
                      <span className={page.is_medical ? 'text-green-400' : 'text-red-400'}>
                        {page.is_medical ? 'Medical' : 'Non-Medical'}
                      </span>
                    </div>
                  </div>
                  
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <p className="text-sm text-gray-400 mb-1">Confidence:</p>
                      <div className="w-full bg-gray-700 rounded-full h-2 mb-1">
                        <div 
                          className={`h-2 rounded-full ${getConfidenceColor(page.confidence)}`}
                          style={{ width: `${(page.confidence * 100).toFixed(1)}%` }}
                        ></div>
                      </div>
                      <p className="text-xs text-right text-gray-400">
                        {(page.confidence * 100).toFixed(1)}%
                      </p>
                    </div>
                    
                    {page.specialty && (
                      <div>
                        <p className="text-sm text-gray-400 mb-1">Specialty:</p>
                        <span className={`inline-block px-2 py-1 rounded text-xs ${getSpecialtyBadgeColor(page.specialty)}`}>
                          {page.specialty}
                        </span>
                      </div>
                    )}
                  </div>
                  
                  {page.terms && page.terms.length > 0 && (
                    <div className="mt-3">
                      <p className="text-sm text-gray-400 mb-1">Medical Terms:</p>
                      <div className="flex flex-wrap gap-1">
                        {page.terms.slice(0, 5).map((term, idx) => (
                          <span key={idx} className="inline-block px-2 py-1 bg-blue-900 text-blue-100 rounded text-xs">
                            {term}
                          </span>
                        ))}
                        {page.terms.length > 5 && (
                          <span className="inline-block px-2 py-1 bg-gray-700 text-gray-300 rounded text-xs">
                            +{page.terms.length - 5} more
                          </span>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}