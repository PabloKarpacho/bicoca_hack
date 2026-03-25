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
  const isLoading = ref(false);
  const submitError = ref<string | null>(null);
  const loadError = ref<string | null>(null);
  const activeDocumentId = ref<string | null>(null);
  const deletingDocumentIds = ref<string[]>([]);

  const asyncJobsStore = useAsyncJobsStore();

  const allDocuments = computed(() =>
    [...items.value].sort((left, right) => right.uploadedAt.localeCompare(left.uploadedAt)),
  );

  const activeDocument = computed(() => {
    const explicitActive =
      items.value.find((item) => item.documentId === activeDocumentId.value) ?? null;
    if (explicitActive) {
      return explicitActive;
    }

    return (
      allDocuments.value.find((item) => !item.status.isTerminal) ??
      allDocuments.value[0] ??
      null
    );
  });

  function isDeletingDocument(documentId: string): boolean {
    return deletingDocumentIds.value.includes(documentId);
  }

  function trackPendingDocuments(nextItems: DocumentListItem[]): void {
    for (const item of nextItems) {
      if (!item.status.isTerminal) {
        startTracking(item.documentId, {
          kind: 'document',
          id: item.documentId,
        });
      }
    }
  }

  async function loadDocuments(): Promise<void> {
    isLoading.value = true;
    loadError.value = null;

    try {
      const loadedItems = await getApiClients().documents.listDocuments();
      items.value = loadedItems;
      trackPendingDocuments(loadedItems);

      if (!activeDocumentId.value || !loadedItems.some((item) => item.documentId === activeDocumentId.value)) {
        activeDocumentId.value =
          loadedItems.find((item) => !item.status.isTerminal)?.documentId ??
          loadedItems[0]?.documentId ??
          null;
      }
    } catch (error) {
      loadError.value = error instanceof Error ? error.message : 'Could not load uploaded resumes';
      throw error;
    } finally {
      isLoading.value = false;
    }
  }

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

  async function deleteDocument(documentId: string): Promise<void> {
    deletingDocumentIds.value = [...deletingDocumentIds.value, documentId];

    try {
      await getApiClients().documents.deleteDocument(documentId);
      asyncJobsStore.stopTracking({
        kind: 'document',
        id: documentId,
      });
      items.value = items.value.filter((item) => item.documentId !== documentId);

      if (activeDocumentId.value === documentId) {
        activeDocumentId.value =
          allDocuments.value.find((item) => !item.status.isTerminal)?.documentId ??
          allDocuments.value[0]?.documentId ??
          null;
      }
    } finally {
      deletingDocumentIds.value = deletingDocumentIds.value.filter((id) => id !== documentId);
    }
  }

  return {
    items,
    allDocuments,
    activeDocumentId,
    activeDocument,
    isLoading,
    isSubmitting,
    submitError,
    loadError,
    deletingDocumentIds,
    isDeletingDocument,
    loadDocuments,
    uploadResume,
    refreshDocumentStatus,
    deleteDocument,
  };
});
