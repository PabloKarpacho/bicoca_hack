<template>
  <q-page class="page-shell">
    <app-page-header
      eyebrow="Resume ingestion"
      title="Upload candidate resumes"
      description="Send CV files to the backend pipeline and monitor processing until the document is ready or failed."
    />

    <q-banner v-if="!apiConfigured" rounded class="bg-warning text-black q-mb-lg">
      API adapter is still a placeholder. The upload form stays interactive for UI testing, but
      real requests will fail until a concrete implementation is wired in
      <span class="text-weight-medium">src/api</span>.
    </q-banner>

    <div class="grid-two-column">
      <upload-cv-form
        :loading="isSubmitting"
        @submit="handleUpload"
      />

      <q-card flat bordered class="app-panel">
        <q-card-section>
          <div class="text-h6">Current processing</div>
          <div class="text-body2 text-grey-7 q-mt-xs">
            Long-running operations are tracked separately from the page through the async job
            store, which is ready for polling-based status updates.
          </div>
        </q-card-section>

        <q-separator />

        <q-card-section>
          <div v-if="activeDocument" class="column q-gutter-md">
            <document-status-card
              :item="activeDocument"
              :deleting="isDeletingDocument(activeDocument.documentId)"
              @refresh="refreshDocumentStatus"
              @delete="handleDelete"
            />
          </div>

          <empty-state
            v-else
            title="No active document"
            caption="Upload a resume to see the current processing state here."
            icon="upload_file"
          />
        </q-card-section>
      </q-card>
    </div>

    <q-banner v-if="submitError" rounded class="bg-negative text-white q-mt-lg">
      {{ submitError }}
    </q-banner>

    <q-banner v-if="loadError" rounded class="bg-negative text-white q-mt-lg">
      {{ loadError }}
    </q-banner>

    <section class="q-mt-xl column q-gutter-md">
      <div>
        <div class="text-h6">All uploaded resumes</div>
        <div class="text-body2 text-grey-7 q-mt-xs">
          Complete upload history from the backend, including documents that are still processing,
          completed resumes, and failed runs.
        </div>
      </div>

      <div v-if="isLoading" class="row items-center q-gutter-sm text-grey-7">
        <q-spinner-gears size="24px" color="primary" />
        <span>Loading uploaded resumes...</span>
      </div>

      <document-status-card
        v-for="item in allDocuments"
        :key="item.documentId"
        :item="item"
        :deleting="isDeletingDocument(item.documentId)"
        @refresh="refreshDocumentStatus"
        @delete="handleDelete"
      />

      <empty-state
        v-if="!isLoading && allDocuments.length === 0"
        title="No uploads yet"
        caption="The upload history will appear here after the first accepted document."
        icon="folder_open"
      />
    </section>
  </q-page>
</template>

<script setup lang="ts">
import { onMounted } from 'vue';
import { isApiConfigured } from '../api';
import { useDocumentUpload } from '../composables/useDocumentUpload';
import AppPageHeader from '../components/AppPageHeader.vue';
import DocumentStatusCard from '../components/documents/DocumentStatusCard.vue';
import UploadCvForm from '../components/documents/UploadCvForm.vue';
import EmptyState from '../components/shared/EmptyState.vue';

const apiConfigured = isApiConfigured();
const {
  activeDocument,
  allDocuments,
  isLoading,
  isSubmitting,
  submitError,
  loadError,
  loadDocuments,
  uploadResume,
  refreshDocumentStatus,
  deleteDocument,
  isDeletingDocument,
} = useDocumentUpload();

onMounted(() => {
  void loadDocuments();
});

async function handleUpload(file: File): Promise<void> {
  await uploadResume(file);
}

async function handleDelete(documentId: string): Promise<void> {
  const confirmed = window.confirm(
    'Delete this resume and remove it from the uploaded documents list?',
  );
  if (!confirmed) {
    return;
  }

  await deleteDocument(documentId);
}
</script>
