import type { AsyncTrackingTarget } from './jobs';

export type DocumentProcessingState =
  | 'accepted'
  | 'queued'
  | 'processing'
  | 'completed'
  | 'failed';

export interface UploadedDocumentReference {
  documentId: string;
  fileName: string;
  uploadedAt: string;
  candidateId?: string | null;
  resumeUrl?: string | null;
}

export interface DocumentProcessingStatus {
  documentId: string;
  state: DocumentProcessingState;
  stageLabel?: string | null;
  message?: string | null;
  errorMessage?: string | null;
  isTerminal: boolean;
  updatedAt?: string | null;
}

export interface DocumentSubmissionReceipt {
  document: UploadedDocumentReference;
  trackingTarget?: AsyncTrackingTarget | null;
  status?: DocumentProcessingStatus | null;
  message?: string | null;
}

export interface DocumentListItem extends UploadedDocumentReference {
  status: DocumentProcessingStatus;
}

export function createAcceptedDocumentStatus(documentId: string): DocumentProcessingStatus {
  return {
    documentId,
    state: 'accepted',
    stageLabel: 'Accepted',
    message: 'Document has been accepted for processing',
    isTerminal: false,
    updatedAt: new Date().toISOString(),
  };
}
