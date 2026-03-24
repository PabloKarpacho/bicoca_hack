<template>
  <q-page class="page-shell">
    <app-page-header
      eyebrow="Candidate search"
      title="Build a shortlist"
      description="Configure practical rule-based filters, trigger the search flow, and review candidate matches with direct resume actions."
    />

    <q-banner v-if="!apiConfigured" rounded class="bg-warning text-black q-mb-lg">
      Search actions are wired through the API abstraction layer but no concrete backend adapter is
      configured yet.
    </q-banner>

    <div class="column q-gutter-lg">
      <q-card flat bordered class="app-panel">
        <q-card-section class="row items-start justify-between q-col-gutter-md">
          <div class="col">
            <div class="text-h6">Prepare filters from vacancy text</div>
            <div class="text-body2 text-grey-7 q-mt-xs">
              Paste a job description, call `/rag/jobs/prepare`, then refine the parsed rules below before running the search.
            </div>
          </div>

          <div class="col-auto row q-gutter-sm">
            <q-btn
              flat
              label="Clear text"
              :disable="isPreparingJob || isLoading || !jobDescription"
              @click="setJobDescription('')"
            />
            <q-btn
              color="primary"
              icon="auto_fix_high"
              label="Prepare rules"
              :loading="isPreparingJob"
              :disable="!apiConfigured || isLoading || !canPrepareJob"
              @click="prepareJobSearch()"
            />
          </div>
        </q-card-section>

        <q-separator />

        <q-card-section class="column q-gutter-md">
          <q-input
            v-model="jobDescription"
            type="textarea"
            autogrow
            filled
            :disable="!apiConfigured || isPreparingJob || isLoading"
            label="Vacancy description"
            hint="The parsed response will populate the rule filters below."
          />

          <q-banner
            v-if="prepareErrorMessage"
            rounded
            class="bg-negative text-white"
          >
            {{ prepareErrorMessage }}
          </q-banner>
        </q-card-section>
      </q-card>

      <candidate-search-filters-form
        :model-value="filters"
        :loading="isLoading || isPreparingJob"
        :disabled="!apiConfigured"
        @update:model-value="setFilters"
        @reset="resetFilters"
      />

      <candidate-search-results
        :results="results"
        :loading="isLoading"
        :error-message="errorMessage"
        :has-searched="hasSearched"
      />
    </div>
  </q-page>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { isApiConfigured } from '../api';
import AppPageHeader from '../components/AppPageHeader.vue';
import CandidateSearchFiltersForm from '../components/search/CandidateSearchFiltersForm.vue';
import CandidateSearchResults from '../components/search/CandidateSearchResults.vue';
import { useCandidateSearch } from '../composables/useCandidateSearch';

const apiConfigured = isApiConfigured();
const {
  errorMessage,
  filters,
  hasSearched,
  isLoading,
  isPreparingJob,
  jobDescription,
  prepareErrorMessage,
  results,
  prepareJobSearch,
  resetFilters,
  setFilters,
  setJobDescription,
} = useCandidateSearch();

const canPrepareJob = computed(() => jobDescription.value.trim().length > 0);
</script>
