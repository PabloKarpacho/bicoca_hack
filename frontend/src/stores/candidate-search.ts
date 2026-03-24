import { ref, watch } from 'vue';
import { defineStore } from 'pinia';
import { getApiClients } from '../api';
import type {
  CandidateSearchFilters,
  CandidateSearchResponse,
  JobSearchPreparationInput,
  LanguageRequirementFilter,
} from '../types/search';
import {
  createDefaultCandidateSearchFilters,
  createEmptySearchResponse,
} from '../types/search';

function cloneLanguages(languages: LanguageRequirementFilter[]): LanguageRequirementFilter[] {
  return languages.map((item) => ({ ...item }));
}

function cloneFilters(filters: CandidateSearchFilters): CandidateSearchFilters {
  return {
    ...filters,
    currentRoles: [...filters.currentRoles],
    seniority: [...filters.seniority],
    languages: cloneLanguages(filters.languages),
    includeSkills: [...filters.includeSkills],
    optionalSkills: [...filters.optionalSkills],
    locations: [...filters.locations],
    domains: [...filters.domains],
    remotePolicies: [...filters.remotePolicies],
    employmentTypes: [...filters.employmentTypes],
    educationRequirements: [...filters.educationRequirements],
    certificationRequirements: [...filters.certificationRequirements],
  };
}

export const useCandidateSearchStore = defineStore('candidate-search', () => {
  let searchDebounceTimer: ReturnType<typeof setTimeout> | null = null;
  let latestSearchToken = 0;

  const filters = ref<CandidateSearchFilters>(createDefaultCandidateSearchFilters());
  const results = ref<CandidateSearchResponse>(createEmptySearchResponse(filters.value));
  const isLoading = ref(false);
  const isPreparingJob = ref(false);
  const errorMessage = ref<string | null>(null);
  const prepareErrorMessage = ref<string | null>(null);
  const jobDescription = ref('');
  const hasSearched = ref(false);

  function clearScheduledSearch(): void {
    if (searchDebounceTimer !== null) {
      clearTimeout(searchDebounceTimer);
      searchDebounceTimer = null;
    }
  }

  function scheduleSearch(delayMs = 350): void {
    clearScheduledSearch();
    searchDebounceTimer = setTimeout(() => {
      searchDebounceTimer = null;
      void runSearch();
    }, delayMs);
  }

  function setFilters(nextFilters: CandidateSearchFilters): void {
    filters.value = cloneFilters(nextFilters);
  }

  function resetFilters(): void {
    filters.value = createDefaultCandidateSearchFilters();
    results.value = createEmptySearchResponse(filters.value);
    errorMessage.value = null;
    prepareErrorMessage.value = null;
    hasSearched.value = false;
  }

  function setJobDescription(value: string): void {
    jobDescription.value = value;
  }

  async function prepareJobSearch(
    input: JobSearchPreparationInput = { rawText: jobDescription.value },
  ): Promise<CandidateSearchFilters> {
    const rawText = input.rawText.trim();

    if (!rawText) {
      prepareErrorMessage.value = 'Paste a vacancy description before preparing filters.';
      throw new Error(prepareErrorMessage.value);
    }

    isPreparingJob.value = true;
    prepareErrorMessage.value = null;

    try {
      const response = await getApiClients().search.prepareJobSearch({
        ...input,
        rawText,
      });
      filters.value = cloneFilters(response);
      errorMessage.value = null;
      hasSearched.value = false;
      return response;
    } catch (error) {
      prepareErrorMessage.value =
        error instanceof Error ? error.message : 'Job preparation failed';
      throw error;
    } finally {
      isPreparingJob.value = false;
    }
  }

  async function runSearch(): Promise<CandidateSearchResponse> {
    clearScheduledSearch();
    const currentSearchToken = ++latestSearchToken;
    isLoading.value = true;
    errorMessage.value = null;

    try {
      const response = await getApiClients().search.searchCandidates(filters.value);
      if (currentSearchToken !== latestSearchToken) {
        return results.value;
      }
      results.value = response;
      hasSearched.value = true;
      return response;
    } catch (error) {
      if (currentSearchToken !== latestSearchToken) {
        return results.value;
      }
      errorMessage.value = error instanceof Error ? error.message : 'Search failed';
      hasSearched.value = true;
      throw error;
    } finally {
      if (currentSearchToken === latestSearchToken) {
        isLoading.value = false;
      }
    }
  }

  watch(
    filters,
    () => {
      scheduleSearch();
    },
    { deep: true },
  );

  return {
    filters,
    results,
    isLoading,
    isPreparingJob,
    errorMessage,
    prepareErrorMessage,
    jobDescription,
    hasSearched,
    setFilters,
    setJobDescription,
    resetFilters,
    prepareJobSearch,
  };
});
