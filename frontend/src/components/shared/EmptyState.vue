<template>
  <div class="column items-center justify-center q-pa-xl text-center app-empty-state">
    <q-icon :name="icon" size="40px" color="grey-5" />
    <div class="text-h6 q-mt-md">{{ title }}</div>
    <p class="text-body2 text-grey-7 q-mt-sm q-mb-none">{{ caption }}</p>
    <slot></slot>
  </div>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    title: string;
    caption: string;
    icon?: string;
  }>(),
  {
    icon: 'inbox',
  },
);
</script>
