'use client';

import React from 'react';
import Navigation from '../components/core/Navigation';

export default function Home() {
  return (
    <div className="min-h-[80vh]">
      <div className="mb-8">
        {/* <h2 className="text-2xl font-bold mb-2 dark:text-white">Document Analysis Dashboard</h2>
        <p className="text-gray-600 dark:text-gray-400">
          Upload and analyze documents for duplicates, medical content, and more.
        </p> */}
      </div>
      
      <Navigation />
    </div>
  );
}