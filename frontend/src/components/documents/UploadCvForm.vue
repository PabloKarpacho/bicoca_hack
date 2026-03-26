<template>
  <q-card flat bordered class="app-panel">
    <q-card-section>
      <div class="text-h6">Upload resume</div>
      <div class="text-body2 text-grey-7 q-mt-xs">
        Select a resume file and send it to the backend processing pipeline.
      </div>
    </q-card-section>

    <q-separator />

    <q-card-section class="column q-gutter-md">
      <q-file
        :model-value="selectedFile"
        label="Resume file"
        filled
        clearable
        accept=".pdf,.doc,.docx"
        @update:model-value="onFileChange"
      >
        <template #prepend>
          <q-icon name="upload_file" />
        </template>
      </q-file>

      <div class="row items-center q-gutter-sm">
        <q-btn
          color="primary"
          label="Send to processing"
          icon="cloud_upload"
          :loading="loading"
          :disable="!selectedFile || disabled"
          @click="submit"
        />
        <q-btn flat label="Reset" :disable="loading || !selectedFile" @click="clearFile" />
      </div>
    </q-card-section>
  </q-card>
</template>

<script setup lang="ts">
import { ref } from 'vue';

const props = withDefaults(
  defineProps<{
    loading?: boolean;
    disabled?: boolean;
  }>(),
  {
    loading: false,
    disabled: false,
  },
);

const emit = defineEmits<{
  submit: [file: File];
}>();

const selectedFile = ref<File | null>(null);

function onFileChange(value: File | null): void {
  selectedFile.value = value instanceof File ? value : null;
}

function clearFile(): void {
  selectedFile.value = null;
}

function submit(): void {
  if (!selectedFile.value || props.disabled) {
    return;
  }

  emit('submit', selectedFile.value);
}
</script>
