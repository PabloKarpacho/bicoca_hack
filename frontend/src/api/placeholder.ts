import type { ApiClients } from './contracts';
import { ApiIntegrationNotConfiguredError } from './errors';

export function createPlaceholderApiClients(): ApiClients {
  return {
    documents: {
      uploadResume: () => Promise.reject(new ApiIntegrationNotConfiguredError()),
      getDocumentStatus: () => Promise.reject(new ApiIntegrationNotConfiguredError()),
    },
    search: {
      prepareJobSearch: () => Promise.reject(new ApiIntegrationNotConfiguredError()),
      searchCandidates: () => Promise.reject(new ApiIntegrationNotConfiguredError()),
      suggestSkills: () => Promise.reject(new ApiIntegrationNotConfiguredError()),
      suggestProfessions: () => Promise.reject(new ApiIntegrationNotConfiguredError()),
    },
    jobs: {
      getAsyncStatus: () => Promise.reject(new ApiIntegrationNotConfiguredError()),
    },
  };
}
