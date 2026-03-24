<template>
  <section class="column q-gutter-md">
    <div class="row items-center justify-between">
      <div>
        <div class="text-h6">Results</div>
        <div class="text-body2 text-grey-7">
          Review the shortlist and open the resume when a link is available.
        </div>
      </div>
      <div v-if="!loading && hasSearched" class="text-body2 text-grey-7">
        {{ results.items.length }} shown / {{ results.total }} total
      </div>
    </div>

    <q-card v-if="loading" flat bordered class="app-panel">
      <q-card-section class="row items-center q-gutter-md">
        <q-spinner color="primary" size="28px" />
        <div>
          <div class="text-subtitle1">Searching candidates</div>
          <div class="text-body2 text-grey-7">
            Rule-based filters are being applied through the API layer.
          </div>
        </div>
      </q-card-section>
    </q-card>

    <q-banner v-else-if="errorMessage" rounded class="bg-negative text-white">
      {{ errorMessage }}
    </q-banner>

    <empty-state
      v-else-if="!hasSearched"
      title="Search not started"
      caption="Update any filter to start building the shortlist."
      icon="travel_explore"
    />

    <empty-state
      v-else-if="results.items.length === 0"
      title="No candidates found"
      caption="Relax one or more filters and the shortlist will refresh automatically."
      icon="person_search"
    />

    <candidate-result-card
      v-for="item in results.items"
      v-else
      :key="`${item.candidateId}:${item.documentId ?? 'none'}`"
      :result="item"
    />
  </section>
</template>

<script setup lang="ts">
import type { CandidateSearchResponse } from '../../types/search';
import CandidateResultCard from './CandidateResultCard.vue';
import EmptyState from '../shared/EmptyState.vue';

defineProps<{
  results: CandidateSearchResponse;
  loading: boolean;
  hasSearched: boolean;
  errorMessage?: string | null;
}>();
</script>
