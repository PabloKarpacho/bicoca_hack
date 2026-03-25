import { storeToRefs } from 'pinia';
import { useDocumentsStore } from '../stores/documents';

export function useDocumentUpload() {
  const store = useDocumentsStore();
  const { activeDocument, allDocuments, isLoading, isSubmitting, submitError, loadError } =
    storeToRefs(store);

  return {
    activeDocument,
    allDocuments,
    isLoading,
    isSubmitting,
    submitError,
    loadError,
    loadDocuments: store.loadDocuments,
    uploadResume: store.uploadResume,
    refreshDocumentStatus: store.refreshDocumentStatus,
    deleteDocument: store.deleteDocument,
    isDeletingDocument: store.isDeletingDocument,
  };
}
