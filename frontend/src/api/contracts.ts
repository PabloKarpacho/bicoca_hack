import type {
  DocumentProcessingStatus,
  DocumentSubmissionReceipt,
} from '../types/documents';
import type { AsyncJobSnapshot, AsyncTrackingTarget } from '../types/jobs';
import type {
  CandidateSearchFilters,
  CandidateSearchResponse,
  JobSearchPreparationInput,
  SkillSuggestion,
} from '../types/search';

export interface DocumentsApi {
  uploadResume(file: File): Promise<DocumentSubmissionReceipt>;
  getDocumentStatus(documentId: string): Promise<DocumentProcessingStatus>;
}

export interface SearchApi {
  prepareJobSearch(input: JobSearchPreparationInput): Promise<CandidateSearchFilters>;
  searchCandidates(filters: CandidateSearchFilters): Promise<CandidateSearchResponse>;
  suggestSkills(query: string): Promise<SkillSuggestion[]>;
  suggestProfessions(query: string): Promise<SkillSuggestion[]>;
}

export interface JobsApi {
  getAsyncStatus(target: AsyncTrackingTarget): Promise<AsyncJobSnapshot>;
}

export interface ApiClients {
  documents: DocumentsApi;
  search: SearchApi;
  jobs: JobsApi;
}
