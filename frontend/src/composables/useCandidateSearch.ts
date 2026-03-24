import { storeToRefs } from 'pinia';
import { useCandidateSearchStore } from '../stores/candidate-search';

export function useCandidateSearch() {
  const store = useCandidateSearchStore();
  const {
    errorMessage,
    filters,
    hasSearched,
    isLoading,
    isPreparingJob,
    jobDescription,
    prepareErrorMessage,
    results,
  } = storeToRefs(store);

  return {
    errorMessage,
    filters,
    hasSearched,
    isLoading,
    isPreparingJob,
    jobDescription,
    prepareErrorMessage,
    results,
    setFilters: store.setFilters,
    setJobDescription: store.setJobDescription,
    resetFilters: store.resetFilters,
    prepareJobSearch: store.prepareJobSearch,
  };
}
