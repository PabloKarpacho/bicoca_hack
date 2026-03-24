<template>
  <q-card flat bordered class="app-panel">
    <q-card-section class="row items-start justify-between q-col-gutter-md">
      <div class="col">
        <div class="text-subtitle1">{{ item.fileName }}</div>
        <div class="text-body2 text-grey-7">
          Accepted {{ formatDateTime(item.uploadedAt) }}
        </div>
      </div>

      <status-chip :status="item.status.state" :label="item.status.stageLabel ?? undefined" />
    </q-card-section>

    <q-separator />

    <q-card-section class="column q-gutter-sm">
      <div class="text-body2">
        {{ item.status.message || 'Status details are not available yet.' }}
      </div>

      <div v-if="item.status.errorMessage" class="text-negative text-body2">
        {{ item.status.errorMessage }}
      </div>

      <div class="row q-col-gutter-md text-body2 text-grey-7">
        <div class="col-auto">Document ID: {{ item.documentId }}</div>
        <div class="col-auto">Updated: {{ formatDateTime(item.status.updatedAt) }}</div>
      </div>
    </q-card-section>

    <q-card-actions align="between">
      <q-btn flat icon="refresh" label="Refresh status" @click="$emit('refresh', item.documentId)" />
      <q-btn
        color="primary"
        outline
        icon="description"
        label="Open resume"
        target="_blank"
        rel="noopener"
        :disable="!item.resumeUrl"
        :href="item.resumeUrl ?? undefined"
      />
    </q-card-actions>
  </q-card>
</template>

<script setup lang="ts">
import type { DocumentListItem } from '../../types/documents';
import { formatDateTime } from '../../utils/formatting';
import StatusChip from '../shared/StatusChip.vue';

defineProps<{
  item: DocumentListItem;
}>();

defineEmits<{
  refresh: [documentId: string];
}>();
</script>
