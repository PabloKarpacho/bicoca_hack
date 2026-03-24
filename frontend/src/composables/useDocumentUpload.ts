import { storeToRefs } from 'pinia';
import { useDocumentsStore } from '../stores/documents';

export function useDocumentUpload() {
  const store = useDocumentsStore();
  const { activeDocument, isSubmitting, recentDocuments, submitError } = storeToRefs(store);

  return {
    activeDocument,
    isSubmitting,
    recentDocuments,
    submitError,
    uploadResume: store.uploadResume,
    refreshDocumentStatus: store.refreshDocumentStatus,
  };
}
