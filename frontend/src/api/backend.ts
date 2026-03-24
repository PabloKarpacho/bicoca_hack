import type { ApiClients } from './contracts';
import type {
  DocumentProcessingState,
  DocumentProcessingStatus,
  DocumentSubmissionReceipt,
} from '../types/documents';
import type { AsyncJobSnapshot, AsyncTrackingTarget } from '../types/jobs';
import type {
  CandidateSearchFilters,
  CandidateSearchResponse,
  CandidateSearchResultItem,
  JobSearchPreparationInput,
  LanguageRequirementFilter,
  SkillSourceType,
  SkillSuggestion,
} from '../types/search';
import { createDefaultCandidateSearchFilters } from '../types/search';
import { apiRequest } from './http';

interface BackendUploadResponse {
  document_id: string;
  candidate_id: string;
  status: string;
  checksum_sha256: string;
  duplicate: boolean;
  pipeline_status_url?: string | null;
}

interface BackendPipelineStage {
  stage: string;
  status: string;
  error_message?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
}

interface BackendPipelineStatusResponse {
  document_id: string;
  candidate_id: string;
  processing_status: string;
  indexing_status: string;
  current_stage: string;
  is_terminal: boolean;
  text_available: boolean;
  storage_available: boolean;
  error_message?: string | null;
  raw_text_extraction?: BackendPipelineStage | null;
  entity_extraction?: BackendPipelineStage | null;
  vector_indexing?: BackendPipelineStage | null;
  updated_at: string;
}

interface BackendCandidateSearchLanguageFilter {
  language_normalized: string;
  min_proficiency_normalized?: string | null;
}

interface BackendCandidateSearchFilters {
  job_id?: string | null;
  source_document_id?: string | null;
  title_raw?: string | null;
  query_text?: string | null;
  query_text_responsibilities?: string | null;
  query_text_skills?: string | null;
  current_title_normalized?: string[] | null;
  seniority_normalized?: string[] | null;
  min_total_experience_months?: number | null;
  employment_types?: string[] | null;
  employment_type?: string | null;
  location_normalized?: string[] | null;
  remote_policies?: string[] | null;
  languages?: BackendCandidateSearchLanguageFilter[] | null;
  require_all_languages?: boolean;
  include_skills?: string[] | null;
  optional_skills?: string[] | null;
  require_all_skills?: boolean;
  skill_source_type?: SkillSourceType;
  domains?: string[] | null;
  degree_normalized?: string[] | null;
  certifications?: string[] | null;
  limit: number;
  offset: number;
}

interface BackendJobSearchPreparationRequest {
  raw_text: string;
  job_id?: string | null;
  source_document_id?: string | null;
}

interface BackendCandidateSearchMatchMetadata {
  matched_skills: string[];
  matched_languages: string[];
  matched_employment_types?: string[];
  matched_degrees?: string[];
  matched_fields_of_study?: string[];
  education_match_status?: 'matched' | 'partial' | 'mismatch' | null;
  education_match_note?: string | null;
}

interface BackendCandidateSearchResultItem {
  candidate_id: string;
  document_id: string;
  resume_download_url?: string | null;
  score?: number | null;
  match_score_percent?: number | null;
  match_score_breakdown?:
    | {
        overall_score?: number | null;
        vector_semantic_score?: number | null;
        role_match_score?: number | null;
        skills_match_score?: number | null;
        experience_match_score?: number | null;
        language_match_score?: number | null;
      }
    | null;
  full_name?: string | null;
  current_title_normalized?: string | null;
  seniority_normalized?: string | null;
  total_experience_months?: number | null;
  location_normalized?: string | null;
  remote_policies?: string[] | null;
  matched_chunk_type?: string | null;
  matched_chunk_text_preview?: string | null;
  top_chunks?: Array<Record<string, unknown>> | null;
  match_metadata?: BackendCandidateSearchMatchMetadata | null;
}

interface BackendCandidateSearchResponse {
  total: number;
  items: BackendCandidateSearchResultItem[];
}

interface BackendSkillSuggestion {
  id: number;
  text: string;
}

function mapBackendDocumentState(status: string): DocumentProcessingState {
  switch (status) {
    case 'ready':
      return 'completed';
    case 'failed':
      return 'failed';
    case 'extracting_text':
    case 'raw_text_ready':
      return 'processing';
    case 'uploaded':
    case 'stored':
    default:
      return 'queued';
  }
}

function humanizeStageLabel(value: string): string {
  return value
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function mapPipelineStatus(response: BackendPipelineStatusResponse): DocumentProcessingStatus {
  return {
    documentId: response.document_id,
    state: mapBackendDocumentState(response.processing_status),
    stageLabel: humanizeStageLabel(response.current_stage),
    message:
      response.processing_status === 'failed'
        ? 'Document processing failed'
        : 'Document is being processed by the backend pipeline',
    errorMessage: response.error_message ?? null,
    isTerminal: response.is_terminal,
    updatedAt: response.updated_at,
  };
}

function mapTrackingSnapshot(response: BackendPipelineStatusResponse): AsyncJobSnapshot {
  const documentStatus = mapPipelineStatus(response);
  const asyncState =
    documentStatus.state === 'accepted' || documentStatus.state === 'queued'
      ? 'pending'
      : documentStatus.state;

  return {
    id: response.document_id,
    resourceKind: 'document',
    state: asyncState,
    stageLabel: documentStatus.stageLabel ?? null,
    message: documentStatus.message ?? null,
    errorMessage: documentStatus.errorMessage ?? null,
    isTerminal: documentStatus.isTerminal,
    updatedAt: documentStatus.updatedAt ?? null,
  };
}

function mapLanguages(filters: LanguageRequirementFilter[]): BackendCandidateSearchLanguageFilter[] {
  return filters
    .filter((item) => item.language.trim().length > 0)
    .map((item) => ({
      language_normalized: item.language.trim(),
      min_proficiency_normalized: item.minProficiency?.trim() || null,
    }));
}

function toBackendSearchFilters(filters: CandidateSearchFilters): BackendCandidateSearchFilters {
  return {
    job_id: filters.jobId,
    source_document_id: filters.sourceDocumentId,
    title_raw: filters.titleRaw.trim() || null,
    query_text: filters.queryText.trim() || null,
    query_text_responsibilities: filters.queryTextResponsibilities.trim() || null,
    query_text_skills: filters.queryTextSkills.trim() || null,
    current_title_normalized: filters.currentRoles.length > 0 ? filters.currentRoles : null,
    seniority_normalized: filters.seniority.length > 0 ? filters.seniority : null,
    min_total_experience_months: filters.minExperienceMonths,
    employment_types: filters.employmentTypes.length > 0 ? filters.employmentTypes : null,
    location_normalized: filters.locations.length > 0 ? filters.locations : null,
    remote_policies: filters.remotePolicies.length > 0 ? filters.remotePolicies : null,
    languages: filters.languages.length > 0 ? mapLanguages(filters.languages) : null,
    require_all_languages: filters.requireAllLanguages,
    include_skills: filters.includeSkills.length > 0 ? filters.includeSkills : null,
    optional_skills: filters.optionalSkills.length > 0 ? filters.optionalSkills : null,
    require_all_skills: filters.requireAllSkills,
    skill_source_type: filters.skillSourceType,
    domains: filters.domains.length > 0 ? filters.domains : null,
    degree_normalized:
      filters.educationRequirements.length > 0 ? filters.educationRequirements : null,
    certifications:
      filters.certificationRequirements.length > 0 ? filters.certificationRequirements : null,
    limit: filters.limit,
    offset: filters.offset,
  };
}

function fromBackendSearchFilters(
  filters: BackendCandidateSearchFilters,
): CandidateSearchFilters {
  const defaults = createDefaultCandidateSearchFilters();

  return {
    ...defaults,
    jobId: filters.job_id ?? null,
    sourceDocumentId: filters.source_document_id ?? null,
    titleRaw: filters.title_raw ?? '',
    currentRoles: filters.current_title_normalized ?? [],
    seniority: filters.seniority_normalized ?? [],
    minExperienceMonths: filters.min_total_experience_months ?? null,
    languages:
      filters.languages?.map((item) => ({
        language: item.language_normalized,
        minProficiency: item.min_proficiency_normalized ?? null,
      })) ?? [],
    requireAllLanguages: filters.require_all_languages ?? defaults.requireAllLanguages,
    includeSkills: filters.include_skills ?? [],
    optionalSkills: filters.optional_skills ?? [],
    requireAllSkills: filters.require_all_skills ?? defaults.requireAllSkills,
    skillSourceType: filters.skill_source_type ?? defaults.skillSourceType,
    locations: filters.location_normalized ?? [],
    domains: filters.domains ?? [],
    remotePolicies: filters.remote_policies ?? [],
    employmentTypes: filters.employment_types ?? (filters.employment_type ? [filters.employment_type] : []),
    educationRequirements: filters.degree_normalized ?? [],
    certificationRequirements: filters.certifications ?? [],
    queryText: filters.query_text ?? '',
    queryTextResponsibilities: filters.query_text_responsibilities ?? '',
    queryTextSkills: filters.query_text_skills ?? '',
    limit: filters.limit ?? defaults.limit,
    offset: filters.offset ?? defaults.offset,
  };
}

function mapSearchResultItem(item: BackendCandidateSearchResultItem): CandidateSearchResultItem {
  return {
    candidateId: item.candidate_id,
    documentId: item.document_id,
    displayName: item.full_name?.trim() || item.candidate_id,
    headline: item.current_title_normalized ?? null,
    currentRole: item.current_title_normalized ?? null,
    seniority: item.seniority_normalized ?? null,
    totalExperienceMonths: item.total_experience_months ?? null,
    location: item.location_normalized ?? null,
    summary: item.matched_chunk_text_preview ?? null,
    resumeUrl: item.resume_download_url ?? null,
    score: item.score ?? null,
    matchScorePercent: item.match_score_percent ?? null,
    matchScoreBreakdown: item.match_score_breakdown
      ? {
          overallScore: item.match_score_breakdown.overall_score ?? null,
          vectorSemanticScore: item.match_score_breakdown.vector_semantic_score ?? null,
          roleMatchScore: item.match_score_breakdown.role_match_score ?? null,
          skillsMatchScore: item.match_score_breakdown.skills_match_score ?? null,
          experienceMatchScore: item.match_score_breakdown.experience_match_score ?? null,
          languageMatchScore: item.match_score_breakdown.language_match_score ?? null,
        }
      : null,
    matchedSkills: item.match_metadata?.matched_skills ?? [],
    matchedLanguages: item.match_metadata?.matched_languages ?? [],
    matchMetadata: item.match_metadata
      ? {
          matchedSkills: item.match_metadata.matched_skills,
          matchedLanguages: item.match_metadata.matched_languages,
          matchedEmploymentTypes: item.match_metadata.matched_employment_types ?? [],
          matchedDegrees: item.match_metadata.matched_degrees ?? [],
          matchedFieldsOfStudy: item.match_metadata.matched_fields_of_study ?? [],
          educationMatchStatus: item.match_metadata.education_match_status ?? null,
          educationMatchNote: item.match_metadata.education_match_note ?? null,
        }
      : null,
  };
}

export function createBackendApiClients(): ApiClients {
  return {
    documents: {
      async uploadResume(file: File): Promise<DocumentSubmissionReceipt> {
        const formData = new FormData();
        formData.set('file', file);

        const response = await apiRequest<BackendUploadResponse>('/rag/ingest_file', {
          method: 'POST',
          body: formData,
        });

        return {
          document: {
            documentId: response.document_id,
            fileName: file.name,
            uploadedAt: new Date().toISOString(),
            candidateId: response.candidate_id,
            resumeUrl: null,
          },
          trackingTarget: {
            kind: 'document',
            id: response.document_id,
          },
          status: {
            documentId: response.document_id,
            state: mapBackendDocumentState(response.status),
            stageLabel: humanizeStageLabel(response.status),
            message: 'Document has been accepted for background processing',
            errorMessage: null,
            isTerminal: response.status === 'ready' || response.status === 'failed',
            updatedAt: new Date().toISOString(),
          },
        };
      },

      async getDocumentStatus(documentId: string): Promise<DocumentProcessingStatus> {
        const response = await apiRequest<BackendPipelineStatusResponse>(
          `/rag/file/${documentId}/pipeline-status`,
        );
        return mapPipelineStatus(response);
      },
    },

    search: {
      async prepareJobSearch(input: JobSearchPreparationInput): Promise<CandidateSearchFilters> {
        const payload: BackendJobSearchPreparationRequest = {
          raw_text: input.rawText,
          job_id: input.jobId ?? null,
          source_document_id: input.sourceDocumentId ?? null,
        };

        const response = await apiRequest<BackendCandidateSearchFilters>('/rag/jobs/prepare', {
          method: 'POST',
          body: JSON.stringify(payload),
        });

        return fromBackendSearchFilters(response);
      },

      async searchCandidates(filters: CandidateSearchFilters): Promise<CandidateSearchResponse> {
        const payload = toBackendSearchFilters(filters);
        const response = await apiRequest<BackendCandidateSearchResponse>(
          '/rag/search?search_strategy=hybrid',
          {
            method: 'POST',
            body: JSON.stringify(payload),
          },
        );

        const items = response.items.map(mapSearchResultItem);
        return {
          items,
          total: response.total,
          limit: filters.limit,
          offset: filters.offset,
          hasMore: filters.offset + items.length < response.total,
        };
      },

      async suggestSkills(query: string): Promise<SkillSuggestion[]> {
        const normalizedQuery = query.trim();
        if (!normalizedQuery) {
          return [];
        }

        const response = await apiRequest<BackendSkillSuggestion[]>(
          `/rag/skills/autocomplete?q=${encodeURIComponent(normalizedQuery)}`,
        );
        return response.map((item) => ({
          id: item.id,
          text: item.text,
        }));
      },

      async suggestProfessions(query: string): Promise<SkillSuggestion[]> {
        const normalizedQuery = query.trim();
        if (!normalizedQuery) {
          return [];
        }

        const response = await apiRequest<BackendSkillSuggestion[]>(
          `/rag/professions/autocomplete?q=${encodeURIComponent(normalizedQuery)}`,
        );
        return response.map((item) => ({
          id: item.id,
          text: item.text,
        }));
      },
    },

    jobs: {
      async getAsyncStatus(target: AsyncTrackingTarget): Promise<AsyncJobSnapshot> {
        if (target.kind !== 'document') {
          throw new Error('Only document status tracking is supported by the current backend.');
        }

        const response = await apiRequest<BackendPipelineStatusResponse>(
          `/rag/file/${target.id}/pipeline-status`,
        );
        return mapTrackingSnapshot(response);
      },
    },
  };
}
