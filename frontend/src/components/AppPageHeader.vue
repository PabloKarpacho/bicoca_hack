<template>
  <div class="page-header">
    <div>
      <div class="text-overline text-primary">{{ eyebrow }}</div>
      <h1 class="text-h4 q-my-xs">{{ title }}</h1>
      <p v-if="description" class="text-body1 text-grey-7 q-ma-none">
        {{ description }}
      </p>
    </div>

    <slot name="actions"></slot>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  title: string;
  eyebrow: string;
  description?: string;
}>();
</script>
