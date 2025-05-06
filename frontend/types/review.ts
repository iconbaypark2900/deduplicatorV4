/**
 * Type definitions for all review-related data.
 * These types support the human review workflow.
 */

export type WorkflowType =
  | 'compare'
  | 'intra-compare'
  | 'single'
  | 'batch'
  | 'medical'
  | 'cluster'
  | 'content'
  | 'review';

export type ReviewStatus = 'pending' | 'reviewed' | 'archived';

export type ReviewDecision = 'keep' | 'archive' | 'unsure';

export interface MatchedPage {
  pageNumber: number;
  documentId: string;
  filename: string;
  pageHash?: string;
  imageUrl?: string;
}

export interface FlaggedPage {
  pageNumber: number;
  pageHash: string;
  similarity: number;
  matchedPage: MatchedPage;
  imageUrl?: string;
  status?: 'pending' | 'kept' | 'archived';
}

export interface ReviewHistoryEntry {
  status: ReviewStatus;
  decision: ReviewDecision;
  reviewer: string;
  timestamp: string;
  notes?: string;
}

export interface ReviewData {
  documentId: string;
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
}

export interface ReviewAction {
  documentId: string;
  decision: ReviewDecision;
  notes?: string;
  reviewer: string;
  timestamp: string;
  affectedPages?: string[]; // Page hashes
}

export interface PageReviewAction {
  pageHash: string;
  documentId: string;
  decision: 'keep' | 'remove';
  reviewer: string;
  timestamp: string;
  notes?: string;
}

export interface ReviewStats {
  totalReviewed: number;
  keptCount: number;
  archivedCount: number;
  pendingCount: number;
  reviewers: string[];
  lastReviewDate?: string;
}