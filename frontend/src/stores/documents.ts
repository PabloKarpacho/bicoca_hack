import { computed, ref } from 'vue';
import { defineStore } from 'pinia';
import { getApiClients } from '../api';
import { useAsyncJobsStore } from './async-jobs';
import type {
  DocumentListItem,
  DocumentProcessingState,
  DocumentProcessingStatus,
} from '../types/documents';
import { createAcceptedDocumentStatus } from '../types/documents';
import type { AsyncJobSnapshot, AsyncTrackingTarget } from '../types/jobs';

function mapJobStateToDocumentState(state: AsyncJobSnapshot['state']): DocumentProcessingState {
  switch (state) {
    case 'completed':
      return 'completed';
    case 'failed':
      return 'failed';
    case 'processing':
      return 'processing';
    case 'pending':
    default:
      return 'queued';
  }
}

export const useDocumentsStore = defineStore('documents', () => {
  const items = ref<DocumentListItem[]>([]);
  const isSubmitting = ref(false);
  const submitError = ref<string | null>(null);
  const activeDocumentId = ref<string | null>(null);

  const asyncJobsStore = useAsyncJobsStore();

  const recentDocuments = computed(() =>
    [...items.value].sort((left, right) => right.uploadedAt.localeCompare(left.uploadedAt)),
  );

  const activeDocument = computed(() =>
    items.value.find((item) => item.documentId === activeDocumentId.value) ?? null,
  );

  function upsertDocument(nextItem: DocumentListItem): void {
    const index = items.value.findIndex((item) => item.documentId === nextItem.documentId);
    if (index === -1) {
      items.value = [nextItem, ...items.value];
      return;
    }

    const clone = [...items.value];
    clone.splice(index, 1, nextItem);
    items.value = clone;
  }

  function updateDocumentStatus(documentId: string, status: DocumentProcessingStatus): void {
    const current = items.value.find((item) => item.documentId === documentId);
    if (!current) {
      return;
    }

    upsertDocument({
      ...current,
      status,
    });
  }

  function applyJobSnapshot(documentId: string, snapshot: AsyncJobSnapshot): void {
    updateDocumentStatus(documentId, {
      documentId,
      state: mapJobStateToDocumentState(snapshot.state),
      stageLabel: snapshot.stageLabel ?? null,
      message: snapshot.message ?? null,
      errorMessage: snapshot.errorMessage ?? null,
      isTerminal: snapshot.isTerminal,
      updatedAt: snapshot.updatedAt ?? null,
    });
  }

  function startTracking(documentId: string, target: AsyncTrackingTarget): void {
    asyncJobsStore.startTracking(target, {
      onUpdate: (snapshot) => applyJobSnapshot(documentId, snapshot),
    });
  }

  async function uploadResume(file: File): Promise<DocumentListItem> {
    isSubmitting.value = true;
    submitError.value = null;

    try {
      const receipt = await getApiClients().documents.uploadResume(file);
      const item: DocumentListItem = {
        ...receipt.document,
        status: receipt.status ?? createAcceptedDocumentStatus(receipt.document.documentId),
      };

      activeDocumentId.value = item.documentId;
      upsertDocument(item);

      if (receipt.trackingTarget) {
        startTracking(item.documentId, receipt.trackingTarget);
      }

      return item;
    } catch (error) {
      submitError.value = error instanceof Error ? error.message : 'Upload failed';
      throw error;
    } finally {
      isSubmitting.value = false;
    }
  }

  async function refreshDocumentStatus(documentId: string): Promise<DocumentProcessingStatus> {
    const status = await getApiClients().documents.getDocumentStatus(documentId);
    updateDocumentStatus(documentId, status);
    return status;
  }

  return {
    items,
    recentDocuments,
    activeDocumentId,
    activeDocument,
    isSubmitting,
    submitError,
    uploadResume,
    refreshDocumentStatus,
  };
});
