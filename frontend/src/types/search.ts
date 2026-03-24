export interface LanguageRequirementFilter {
  language: string;
  minProficiency?: string | null;
}

export type SkillSourceType = 'explicit' | 'inferred_from_experience' | 'any';

export interface SkillSuggestion {
  id: number;
  text: string;
}

export interface JobSearchPreparationInput {
  rawText: string;
  jobId?: string | null;
  sourceDocumentId?: string | null;
}

export interface CandidateSearchFilters {
  jobId: string | null;
  sourceDocumentId: string | null;
  titleRaw: string;
  currentRoles: string[];
  seniority: string[];
  minExperienceMonths: number | null;
  languages: LanguageRequirementFilter[];
  requireAllLanguages: boolean;
  includeSkills: string[];
  optionalSkills: string[];
  requireAllSkills: boolean;
  skillSourceType: SkillSourceType;
  locations: string[];
  domains: string[];
  remotePolicies: string[];
  employmentTypes: string[];
  educationRequirements: string[];
  certificationRequirements: string[];
  queryText: string;
  queryTextResponsibilities: string;
  queryTextSkills: string;
  limit: number;
  offset: number;
}

export interface SearchMatchMetadata {
  matchedSkills?: string[];
  matchedLanguages?: string[];
  matchedEmploymentTypes?: string[];
  matchedDegrees?: string[];
  matchedFieldsOfStudy?: string[];
  educationMatchStatus?: 'matched' | 'partial' | 'mismatch' | null;
  educationMatchNote?: string | null;
  matchedDomains?: string[];
  notes?: string[];
}

export interface SearchScoreBreakdown {
  overallScore?: number | null;
  vectorSemanticScore?: number | null;
  roleMatchScore?: number | null;
  skillsMatchScore?: number | null;
  experienceMatchScore?: number | null;
  languageMatchScore?: number | null;
}

export interface CandidateSearchResultItem {
  candidateId: string;
  documentId?: string | null;
  displayName: string;
  headline?: string | null;
  currentRole?: string | null;
  seniority?: string | null;
  totalExperienceMonths?: number | null;
  location?: string | null;
  summary?: string | null;
  resumeUrl?: string | null;
  score?: number | null;
  matchScorePercent?: number | null;
  matchScoreBreakdown?: SearchScoreBreakdown | null;
  matchedSkills?: string[];
  matchedLanguages?: string[];
  matchMetadata?: SearchMatchMetadata | null;
}

export interface CandidateSearchResponse {
  items: CandidateSearchResultItem[];
  total: number;
  limit: number;
  offset: number;
  hasMore: boolean;
}

export const SENIORITY_OPTIONS = ['junior', 'middle', 'senior', 'lead', 'manager'];
export const PROFICIENCY_OPTIONS = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2', 'native'];
export const REMOTE_POLICY_OPTIONS = ['remote', 'hybrid', 'onsite'];
export const EMPLOYMENT_TYPE_OPTIONS = [
  'full_time',
  'part_time',
  'contract',
  'internship',
];
export const EDUCATION_LEVEL_OPTIONS = [
  'secondary',
  'associate',
  'bachelor',
  'master',
  'phd',
];

export function createDefaultCandidateSearchFilters(): CandidateSearchFilters {
  return {
    jobId: null,
    sourceDocumentId: null,
    titleRaw: '',
    currentRoles: [],
    seniority: [],
    minExperienceMonths: null,
    languages: [],
    requireAllLanguages: false,
    includeSkills: [],
    optionalSkills: [],
    requireAllSkills: false,
    skillSourceType: 'any',
    locations: [],
    domains: [],
    remotePolicies: [],
    employmentTypes: [],
    educationRequirements: [],
    certificationRequirements: [],
    queryText: '',
    queryTextResponsibilities: '',
    queryTextSkills: '',
    limit: 20,
    offset: 0,
  };
}

export function createEmptySearchResponse(
  filters: CandidateSearchFilters = createDefaultCandidateSearchFilters(),
): CandidateSearchResponse {
  return {
    items: [],
    total: 0,
    limit: filters.limit,
    offset: filters.offset,
    hasMore: false,
  };
}
