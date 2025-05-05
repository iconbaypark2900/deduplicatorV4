'use client';

import React, { useState, useRef, useEffect } from 'react';
import UploadDropzone from '../core/UploadDropzone';
import { dataScienceService } from '../../services/dataScienceService';
import { ClusteringResult, ClusterNode, ClusterEdge, Cluster } from '../../types/document';
import { ReviewData } from '../../types/review';

interface Props {
  onComplete?: (data: ReviewData) => void;
}

/**
 * Document Clustering component for visualizing relationships between documents.
 * Uses the backend data science module for clustering analysis.
 */
export default function DocumentClustering({ onComplete }: Props) {
  const [result, setResult] = useState<ClusteringResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedCluster, setSelectedCluster] = useState<string | null>(null);
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [visualizationUrl, setVisualizationUrl] = useState<string | null>(null);
  
  const canvasRef = useRef<HTMLCanvasElement>(null);
  
  // Handle file upload and clustering
  const handleUpload = async (files: File[]) => {
    setIsLoading(true);
    setError(null);
    
    try {
      const clusteringResult = await dataScienceService.clusterDocuments(files);
      setResult(clusteringResult);
      
      if (clusteringResult.visualization_url) {
        setVisualizationUrl(clusteringResult.visualization_url);
      }
      
      // If onComplete callback is provided, format data for review
      if (onComplete) {
        onComplete({
          documentId: `cluster-analysis-${Date.now()}`,
          filename: `Cluster Analysis (${clusteringResult.total_documents} documents)`,
          workflowType: 'cluster',
          flaggedPages: [],  // No duplicate flagging in clustering
          status: 'pending',
          reviewHistory: [],
          duplicateConfidence: clusteringResult.total_clusters > 1 ? 0.8 : 0.2,
          medicalConfidence: 0 // We don't know this from clustering
        });
      }
    } catch (error) {
      console.error('Clustering failed:', error);
      setError('Failed to cluster documents. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  // Draw the network visualization on canvas when results change
  useEffect(() => {
    if (!result || !canvasRef.current) return;
    
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    
    // Set canvas size based on its container
    canvas.width = canvas.offsetWidth;
    canvas.height = canvas.offsetHeight;
    
    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    // Calculate scaling to fit nodes
    const padding = 50;
    const xValues = result.nodes.map(node => node.x);
    const yValues = result.nodes.map(node => node.y);
    
    const minX = Math.min(...xValues);
    const maxX = Math.max(...xValues);
    const minY = Math.min(...yValues);
    const maxY = Math.max(...yValues);
    
    const xScale = (canvas.width - padding * 2) / (maxX - minX || 1);
    const yScale = (canvas.height - padding * 2) / (maxY - minY || 1);
    
    // Draw edges first (so they appear behind nodes)
    ctx.globalAlpha = 0.2;
    result.edges.forEach(edge => {
      const source = result.nodes.find(n => n.doc_id === edge.source);
      const target = result.nodes.find(n => n.doc_id === edge.target);
      
      if (!source || !target) return;
      
      const sourceX = (source.x - minX) * xScale + padding;
      const sourceY = (source.y - minY) * yScale + padding;
      const targetX = (target.x - minX) * xScale + padding;
      const targetY = (target.y - minY) * yScale + padding;
      
      // Draw the edge
      ctx.beginPath();
      ctx.moveTo(sourceX, sourceY);
      ctx.lineTo(targetX, targetY);
      ctx.strokeStyle = '#888';
      ctx.lineWidth = edge.weight * 2; // Scale line width by weight
      ctx.stroke();
    });
    
    // Draw nodes on top
    ctx.globalAlpha = 1.0;
    result.nodes.forEach(node => {
      const x = (node.x - minX) * xScale + padding;
      const y = (node.y - minY) * yScale + padding;
      const radius = Math.min(10 + node.connections * 2, 25);
      
      // Determine color based on cluster
      const clusterColors: {[key: string]: string} = {
        '0': '#3498db', // blue
        '1': '#e74c3c', // red
        '2': '#2ecc71', // green
        '3': '#f39c12', // orange
        '4': '#9b59b6', // purple
        '5': '#1abc9c', // teal
        '6': '#d35400', // dark orange
        '7': '#34495e'  // dark blue
      };
      
      // Get cluster number or default to gray
      const color = node.cluster_id ? 
                    clusterColors[node.cluster_id.replace('cluster_', '')] || '#95a5a6' : 
                    '#95a5a6';
                    
      // Highlight selected cluster or hovered node
      const isHighlighted = (selectedCluster && node.cluster_id === selectedCluster) || 
                           (hoveredNode && node.doc_id === hoveredNode);
      
      // Draw node
      ctx.beginPath();
      ctx.arc(x, y, isHighlighted ? radius * 1.2 : radius, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.fill();
      
      // Add outline for highlighted nodes
      if (isHighlighted) {
        ctx.strokeStyle = '#fff';
        ctx.lineWidth = 2;
        ctx.stroke();
      }
    });
    
    // Draw cluster labels
    ctx.font = '14px Arial';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillStyle = '#fff';
    
    result.clusters.forEach(cluster => {
      const x = (cluster.center_x - minX) * xScale + padding;
      const y = (cluster.center_y - minY) * yScale + padding;
      
      ctx.fillText(`Cluster ${cluster.cluster_id.replace('cluster_', '')}`, x, y - 20);
    });
    
  }, [result, selectedCluster, hoveredNode]);
  
  // Handle canvas click to select clusters/nodes
  const handleCanvasClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!result || !canvasRef.current) return;
    
    const canvas = canvasRef.current;
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    
    // Calculate scaling to fit nodes (same as in the drawing effect)
    const padding = 50;
    const xValues = result.nodes.map(node => node.x);
    const yValues = result.nodes.map(node => node.y);
    
    const minX = Math.min(...xValues);
    const maxX = Math.max(...xValues);
    const minY = Math.min(...yValues);
    const maxY = Math.max(...yValues);
    
    const xScale = (canvas.width - padding * 2) / (maxX - minX || 1);
    const yScale = (canvas.height - padding * 2) / (maxY - minY || 1);
    
    // Check if a node was clicked
    for (const node of result.nodes) {
      const nodeX = (node.x - minX) * xScale + padding;
      const nodeY = (node.y - minY) * yScale + padding;
      const radius = Math.min(10 + node.connections * 2, 25);
      
      const distance = Math.sqrt(Math.pow(x - nodeX, 2) + Math.pow(y - nodeY, 2));
      
      if (distance <= radius) {
        // Node clicked
        if (node.cluster_id) {
          setSelectedCluster(node.cluster_id === selectedCluster ? null : node.cluster_id);
        }
        return;
      }
    }
    
    // No node clicked, clear selection
    setSelectedCluster(null);
  };
  
  // Track mouse movement for hover effects
  const handleCanvasMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!result || !canvasRef.current) return;
    
    const canvas = canvasRef.current;
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    
    // Use same scaling as above
    const padding = 50;
    const xValues = result.nodes.map(node => node.x);
    const yValues = result.nodes.map(node => node.y);
    
    const minX = Math.min(...xValues);
    const maxX = Math.max(...xValues);
    const minY = Math.min(...yValues);
    const maxY = Math.max(...yValues);
    
    const xScale = (canvas.width - padding * 2) / (maxX - minX || 1);
    const yScale = (canvas.height - padding * 2) / (maxY - minY || 1);
    
    // Check if mouse is over any node
    let hoveredNodeId = null;
    
    for (const node of result.nodes) {
      const nodeX = (node.x - minX) * xScale + padding;
      const nodeY = (node.y - minY) * yScale + padding;
      const radius = Math.min(10 + node.connections * 2, 25);
      
      const distance = Math.sqrt(Math.pow(x - nodeX, 2) + Math.pow(y - nodeY, 2));
      
      if (distance <= radius) {
        hoveredNodeId = node.doc_id;
        break;
      }
    }
    
    setHoveredNode(hoveredNodeId);
  };
  
  // Clear hover state when mouse leaves canvas
  const handleCanvasMouseLeave = () => {
    setHoveredNode(null);
  };
  
  return (
    <div className="space-y-6">
      <div className="bg-black text-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold mb-4">Document Clustering</h3>
        <p className="text-gray-300 mb-4">
          Upload multiple documents to visualize similarity clusters and relationships between documents.
        </p>
        <UploadDropzone 
          onUpload={handleUpload} 
          mode="multiple"
          label="Upload documents for clustering"
          sublabel="Select multiple PDF files (max 50MB each)"
        />
      </div>

      {isLoading && (
        <div className="flex justify-center items-center py-8">
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
          <span className="ml-3 text-gray-600 dark:text-gray-400">Clustering documents...</span>
        </div>
      )}

      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded dark:bg-red-900/30 dark:text-red-300 dark:border-red-800">
          <p>{error}</p>
        </div>
      )}

      {result && (
        <div className="space-y-6">
          {/* Clustering Summary */}
          <div className="bg-black text-white rounded-lg shadow p-6">
            <h3 className="text-xl font-bold mb-4">Clustering Results</h3>
            
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
              <div className="border border-gray-700 rounded-lg p-4 bg-gray-900">
                <h4 className="text-lg font-semibold text-gray-300">Documents</h4>
                <p className="text-2xl font-bold">{result.total_documents}</p>
              </div>
              
              <div className="border border-gray-700 rounded-lg p-4 bg-gray-900">
                <h4 className="text-lg font-semibold text-gray-300">Clusters</h4>
                <p className="text-2xl font-bold">{result.total_clusters}</p>
              </div>
              
              <div className="border border-gray-700 rounded-lg p-4 bg-gray-900">
                <h4 className="text-lg font-semibold text-gray-300">Largest Cluster</h4>
                <p className="text-2xl font-bold">{result.largest_cluster_size} docs</p>
              </div>
            </div>
            
            {/* Cluster Visualization */}
            {visualizationUrl ? (
              <div className="border border-gray-700 rounded-lg overflow-hidden">
                <img 
                  src={visualizationUrl} 
                  alt="Document Clusters Visualization" 
                  className="w-full h-auto"
                />
              </div>
            ) : (
              <div className="border border-gray-700 rounded-lg overflow-hidden p-2 bg-gray-900">
                <canvas 
                  ref={canvasRef} 
                  className="w-full h-[400px]"
                  onClick={handleCanvasClick}
                  onMouseMove={handleCanvasMouseMove}
                  onMouseLeave={handleCanvasMouseLeave}
                ></canvas>
              </div>
            )}
          </div>
          
          {/* Cluster Details */}
          <div className="bg-black text-white rounded-lg shadow p-6">
            <h3 className="text-xl font-bold mb-4">Cluster Details</h3>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {result.clusters.map(cluster => (
                <div 
                  key={cluster.cluster_id}
                  className={`border rounded-lg p-4 ${
                    selectedCluster === cluster.cluster_id 
                      ? 'border-blue-500 bg-blue-900/20' 
                      : 'border-gray-700 bg-gray-900'
                  } cursor-pointer hover:bg-gray-800 transition-colors`}
                  onClick={() => setSelectedCluster(
                    cluster.cluster_id === selectedCluster ? null : cluster.cluster_id
                  )}
                >
                  <div className="flex justify-between items-center mb-3">
                    <h4 className="font-semibold">
                      Cluster {cluster.cluster_id.replace('cluster_', '')}
                    </h4>
                    <span className="bg-blue-600 text-white px-2 py-1 rounded text-xs">
                      {cluster.documents.length} docs
                    </span>
                  </div>
                  
                  {selectedCluster === cluster.cluster_id && (
                    <div className="mt-3">
                      <h5 className="text-sm text-gray-400 mb-2">Documents in this cluster:</h5>
                      <ul className="space-y-1 max-h-40 overflow-y-auto">
                        {result.nodes
                          .filter(node => node.cluster_id === cluster.cluster_id)
                          .map(node => (
                            <li 
                              key={node.doc_id} 
                              className="text-sm text-gray-300 truncate hover:text-white"
                              title={node.filename}
                            >
                              {node.filename}
                            </li>
                          ))
                        }
                      </ul>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
          
          {/* Similarity Network */}
          <div className="bg-black text-white rounded-lg shadow p-6">
            <h3 className="text-xl font-bold mb-4">Document Similarities</h3>
            
            <div className="space-y-4">
              <p className="text-gray-300 text-sm">
                The table below shows the strongest document relationships identified during clustering.
              </p>
              
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-700">
                  <thead>
                    <tr>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">Document 1</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">Document 2</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">Similarity</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-700">
                    {result.edges
                      .sort((a, b) => b.weight - a.weight)
                      .slice(0, 10)
                      .map((edge, idx) => {
                        const source = result.nodes.find(n => n.doc_id === edge.source);
                        const target = result.nodes.find(n => n.doc_id === edge.target);
                        
                        if (!source || !target) return null;
                        
                        return (
                          <tr key={idx} className={idx % 2 === 0 ? 'bg-gray-900' : ''}>
                            <td className="px-4 py-2 whitespace-nowrap text-sm">
                              <div className="text-gray-300 truncate max-w-[200px]" title={source.filename}>
                                {source.filename}
                              </div>
                            </td>
                            <td className="px-4 py-2 whitespace-nowrap text-sm">
                              <div className="text-gray-300 truncate max-w-[200px]" title={target.filename}>
                                {target.filename}
                              </div>
                            </td>
                            <td className="px-4 py-2 whitespace-nowrap text-sm">
                              <div className="flex items-center">
                                <div className="w-full bg-gray-700 h-2 rounded-full mr-2">
                                  <div 
                                    className="bg-blue-500 h-2 rounded-full" 
                                    style={{ width: `${edge.weight * 100}%` }}
                                  ></div>
                                </div>
                                <span className="text-gray-300 whitespace-nowrap">
                                  {(edge.weight * 100).toFixed(1)}%
                                </span>
                              </div>
                            </td>
                          </tr>
                        );
                      })
                    }
                  </tbody>
                </table>
              </div>
              
              {result.edges.length > 10 && (
                <p className="text-gray-400 text-xs text-right mt-2">
                  Showing top 10 of {result.edges.length} connections
                </p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}