<template>
  <q-chip square :color="tone.color" :text-color="tone.textColor" :icon="tone.icon">
    {{ label }}
  </q-chip>
</template>

<script setup lang="ts">
import { computed } from 'vue';

const props = defineProps<{
  status: string;
  label?: string | null | undefined;
}>();

const tone = computed(() => {
  switch (props.status) {
    case 'completed':
      return { color: 'positive', textColor: 'white', icon: 'check_circle' };
    case 'failed':
      return { color: 'negative', textColor: 'white', icon: 'error' };
    case 'processing':
      return { color: 'warning', textColor: 'black', icon: 'autorenew' };
    case 'accepted':
    case 'queued':
    case 'pending':
      return { color: 'info', textColor: 'white', icon: 'schedule' };
    default:
      return { color: 'grey-5', textColor: 'black', icon: 'help_outline' };
  }
});

const label = computed(() => props.label ?? props.status);
</script>
