'use client';

import React, { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';

interface Props {
  onUpload: (files: File | File[]) => void | Promise<void>;
  mode: 'single' | 'multiple';
  label?: string;
  sublabel?: string;
  maxSize?: number;
  acceptedFileTypes?: string[];
}

/**
 * Reusable file upload component with drag-and-drop functionality.
 * Supports both single and multiple file uploads.
 */
export default function UploadDropzone({
  onUpload,
  mode = 'single',
  label = 'Drop files here or click to browse',
  sublabel = 'PDF files only (max 50MB)',
  maxSize = 50 * 1024 * 1024, // 50MB default
  acceptedFileTypes = ['application/pdf']
}: Props) {
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadedFiles, setUploadedFiles] = useState<File[]>([]);

  const handleUpload = async (files: File | File[]) => {
    const arr = Array.isArray(files) ? files : [files];
    setUploadError(null);
    
    // Filter out files that exceed the size limit
    const validFiles = arr.filter(file => file.size <= maxSize);
    const oversizedFiles = arr.filter(file => file.size > maxSize);
    
    if (oversizedFiles.length > 0) {
      setUploadError(`${oversizedFiles.length} file(s) exceeded the ${maxSize / (1024 * 1024)}MB limit and were skipped.`);
    }
    
    if (validFiles.length === 0) {
      return;
    }
    
    setUploadedFiles(mode === 'single' ? [validFiles[0]] : validFiles);
    
    try {
      setIsUploading(true);
      // Pass either a single file or array of files based on mode
      await onUpload(mode === 'single' ? validFiles[0] : validFiles);
    } catch (error) {
      console.error("Upload processing error:", error);
      setUploadError('An error occurred while processing your upload.');
    } finally {
      setIsUploading(false);
    }
  };

  const { getRootProps, getInputProps, isDragActive, fileRejections } = useDropzone({
    onDrop: handleUpload,
    accept: {
      'application/pdf': ['.pdf']
    },
    maxSize,
    multiple: mode === 'multiple',
  });

  return (
    <div className="space-y-4">
      <div
        {...getRootProps()}
        className={`p-8 border-2 border-dashed rounded-lg flex flex-col items-center justify-center cursor-pointer transition-colors ${
          isDragActive
            ? 'border-accent-primary bg-accent-primary/10'
            : 'border-accent-secondary/30 bg-surface'
        }`}
      >
        <input {...getInputProps()} />
        
        <div className="text-center">
          <svg
            className={`mx-auto h-12 w-12 ${
              isDragActive ? 'text-accent-primary' : 'text-accent-secondary'
            }`}
            stroke="currentColor"
            fill="none"
            viewBox="0 0 48 48"
            aria-hidden="true"
          >
            <path
              d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02"
              strokeWidth={2}
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          
          <p className="mt-2 text-sm font-medium text-text-primary">
            {label}
          </p>
          <p className="mt-1 text-xs text-text-secondary">
            {sublabel}
          </p>
        </div>
      </div>
      
      {isUploading && (
        <div className="flex items-center justify-center">
          <div className="w-4 h-4 rounded-full bg-info animate-pulse mr-2"></div>
          <p className="text-sm text-text-secondary">Uploading...</p>
        </div>
      )}
      
      {uploadError && (
        <div className="text-sm text-error">
          {uploadError}
        </div>
      )}
      
      {uploadedFiles.length > 0 && !isUploading && (
        <div className="text-sm text-success">
          {uploadedFiles.length} file(s) uploaded successfully.
        </div>
      )}
    </div>
  );
}