from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.models.common_types import (
    CandidateSkillSearchSourceLiteral,
    EducationLiteral,
    EducationMatchStatusLiteral,
    EmploymentTypeLiteral,
    ProficiencyLiteral,
    RemotePolicyLiteral,
    SeniorityLiteral,
    VectorChunkTypeLiteral,
)
from typing import Literal

SortByLiteral = Literal["created_at", "updated_at", "total_experience_months", "full_name"]
SortOrderLiteral = Literal["asc", "desc"]


class CandidateLanguageFilter(BaseModel):
    language_normalized: str = Field(description="Canonical language name used in candidate filtering.")
    min_proficiency_normalized: ProficiencyLiteral | None = Field(
        default=None,
        description="Minimum acceptable language proficiency for this language filter.",
    )


class CandidateSearchFilters(BaseModel):
    job_id: str | None = Field(default=None, description="Prepared job search identifier when the search originates from a job.")
    source_document_id: str | None = Field(
        default=None,
        description="Source document identifier that produced the prepared search request, if any.",
    )
    title_raw: str | None = Field(default=None, description="Original job title or search title text.")
    query_text: str | None = Field(
        default=None,
        description="Main semantic query text used for vector search.",
    )
    query_text_responsibilities: str | None = Field(
        default=None,
        description="Optional semantic query focused on responsibilities and activities.",
    )
    query_text_skills: str | None = Field(
        default=None,
        description="Optional semantic query focused on skills and technology signals.",
    )
    candidate_ids: list[str] | None = Field(
        default=None,
        description="Optional shortlist of candidate identifiers to constrain the search scope.",
    )
    current_title_normalized: list[str] | None = Field(
        default=None,
        description="Candidate current title filters using normalized profession labels.",
    )
    seniority_normalized: list[SeniorityLiteral] | None = Field(
        default=None,
        description="Allowed normalized seniority values for candidate filtering.",
    )
    min_total_experience_months: int | None = Field(
        default=None,
        description="Minimum total candidate experience in months.",
    )
    max_total_experience_months: int | None = Field(
        default=None,
        description="Maximum total candidate experience in months.",
    )
    location_normalized: list[str] | None = Field(
        default=None,
        description="Normalized candidate locations used in structured filtering.",
    )
    remote_policies: list[RemotePolicyLiteral] | None = Field(
        default=None,
        description="Allowed remote work arrangements for candidate filtering.",
    )
    employment_types: list[EmploymentTypeLiteral] | None = Field(
        default=None,
        description="Allowed employment types for candidate filtering.",
    )

    languages: list[CandidateLanguageFilter] | None = Field(
        default=None,
        description="Structured language requirements applied to candidates.",
    )
    require_all_languages: bool = Field(
        default=False,
        description="Whether all language filters must match instead of any matching language.",
    )

    include_skills: list[str] | None = Field(
        default=None,
        description="Required skills used in structured and semantic matching.",
    )
    optional_skills: list[str] | None = Field(
        default=None,
        description="Nice-to-have skills used as supportive matching signals.",
    )
    require_all_skills: bool = Field(
        default=False,
        description="Whether all required skills must match instead of any overlap being sufficient.",
    )
    skill_source_type: CandidateSkillSearchSourceLiteral = Field(
        default="any",
        description="Which candidate skill source types are considered during matching.",
    )

    current_or_past_titles: list[str] | None = Field(
        default=None,
        description="Normalized or raw titles that can match current or historical experience.",
    )
    companies: list[str] | None = Field(
        default=None,
        description="Company filters applied to candidate experience history.",
    )
    domains: list[str] | None = Field(
        default=None,
        description="Domain or industry filters used as structured or semantic signals.",
    )
    min_relevant_experience_months: int | None = Field(
        default=None,
        description="Minimum experience in the relevant title or domain, in months.",
    )
    is_currently_employed_in_title: bool | None = Field(
        default=None,
        description="Whether the candidate must currently hold the matching role or title.",
    )

    degree_normalized: list[EducationLiteral] | None = Field(
        default=None,
        description="Allowed education degree levels used for education compatibility checks.",
    )
    fields_of_study: list[str] | None = Field(
        default=None,
        description="Allowed education fields of study used in candidate matching.",
    )

    certifications: list[str] | None = Field(
        default=None,
        description="Required or preferred certifications used during candidate matching.",
    )
    chunk_types: list[VectorChunkTypeLiteral] | None = Field(
        default=None,
        description="Explicit vector chunk types to search over. Overrides automatic intent-based selection.",
    )
    score_threshold: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Minimum vector similarity threshold for chunk retrieval. Default is 0.0 to prefer recall-first retrieval.",
    )

    processing_status: str | None = Field(default=None, description="Processing status filter for source documents or profiles.")
    pipeline_version: str | None = Field(default=None, description="Pipeline version filter.")
    model_version: str | None = Field(default=None, description="Model version filter.")
    extraction_confidence: float | None = Field(default=None, description="Minimum or recorded extraction confidence filter.")
    error_message: str | None = Field(default=None, description="Processing error message filter when inspecting failed documents.")
    started_at: datetime | None = Field(default=None, description="Lower-level processing start timestamp filter or metadata carrier.")
    finished_at: datetime | None = Field(default=None, description="Lower-level processing finish timestamp filter or metadata carrier.")

    limit: int = Field(default=20, ge=1, le=100, description="Page size for search results.")
    offset: int = Field(default=0, ge=0, description="Pagination offset for search results.")
    sort_by: SortByLiteral = Field(default="updated_at", description="Primary structured sort field.")
    sort_order: SortOrderLiteral = Field(default="desc", description="Sort direction for structured result ordering.")

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_remote_policy(cls, data):
        if not isinstance(data, dict):
            return data
        if data.get("remote_policies") in (None, []):
            remote_policy = data.get("remote_policy")
            if isinstance(remote_policy, list):
                data["remote_policies"] = remote_policy
            elif isinstance(remote_policy, str) and remote_policy.strip():
                data["remote_policies"] = [remote_policy]
        if data.get("employment_types") in (None, []):
            employment_type = data.get("employment_type")
            if isinstance(employment_type, list):
                data["employment_types"] = employment_type
            elif isinstance(employment_type, str) and employment_type.strip():
                data["employment_types"] = [employment_type]
        return data


class CandidateSearchMatchMetadata(BaseModel):
    matched_skills: list[str] = Field(default_factory=list, description="Skills from the query that matched the candidate.")
    matched_languages: list[str] = Field(default_factory=list, description="Languages from the query that matched the candidate.")
    matched_employment_types: list[EmploymentTypeLiteral] = Field(
        default_factory=list,
        description="Employment types that overlap between the query and the candidate profile.",
    )
    matched_degrees: list[EducationLiteral] = Field(
        default_factory=list,
        description="Education degree levels that overlap between the query and candidate education.",
    )
    matched_fields_of_study: list[str] = Field(
        default_factory=list,
        description="Fields of study that overlap between the query and candidate education.",
    )
    education_match_status: EducationMatchStatusLiteral | None = Field(
        default=None,
        description="Summary education compatibility classification for the candidate.",
    )
    education_match_note: str | None = Field(
        default=None,
        description="Human-readable explanation of the education compatibility result.",
    )


class CandidateSearchScoreBreakdown(BaseModel):
    overall_score: float | None = Field(default=None, description="Final normalized overall match score in the 0..1 range.")
    vector_semantic_score: float | None = Field(default=None, description="Semantic vector relevance component.")
    role_match_score: float | None = Field(default=None, description="Role or profession alignment component.")
    skills_match_score: float | None = Field(default=None, description="Skills overlap component.")
    experience_match_score: float | None = Field(default=None, description="Relevant experience alignment component.")
    language_match_score: float | None = Field(default=None, description="Language compatibility component.")


class CandidateSearchResultItem(BaseModel):
    candidate_id: str = Field(description="Candidate identifier for the search result item.")
    document_id: str = Field(description="Source document identifier for the search result item.")
    resume_download_url: str | None = Field(default=None, description="Backend URL that allows opening or downloading the candidate resume.")
    score: float | None = Field(default=None, description="Raw search score returned by the active search strategy.")
    match_score_percent: int | None = Field(default=None, description="Calibrated explainable match score shown as a percentage.")
    match_score_breakdown: CandidateSearchScoreBreakdown | None = Field(
        default=None,
        description="Component breakdown used to compute the explainable match score.",
    )
    full_name: str | None = Field(default=None, description="Candidate full name.")
    current_title_normalized: str | None = Field(default=None, description="Candidate current normalized title.")
    seniority_normalized: SeniorityLiteral | None = Field(default=None, description="Candidate normalized seniority.")
    total_experience_months: int | None = Field(default=None, description="Candidate total experience in months.")
    location_normalized: str | None = Field(default=None, description="Candidate normalized location label.")
    remote_policies: list[RemotePolicyLiteral] | None = Field(
        default=None,
        description="Candidate remote work arrangements or preferences.",
    )
    matched_chunk_type: VectorChunkTypeLiteral | None = Field(
        default=None,
        description="Highest-impact vector chunk type that matched the candidate.",
    )
    matched_chunk_text_preview: str | None = Field(
        default=None,
        description="Short preview of the best matching vector chunk text.",
    )
    top_chunks: list[dict] | None = Field(
        default=None,
        description="Top vector chunk matches that contributed to the candidate score.",
    )
    match_metadata: CandidateSearchMatchMetadata | None = Field(
        default=None,
        description="Structured metadata describing explicit overlaps between the query and candidate.",
    )


class CandidateSearchResult(BaseModel):
    total: int = Field(description="Total number of matching candidates before pagination.")
    items: list[CandidateSearchResultItem] = Field(description="Paginated candidate search results.")
    applied_filters: CandidateSearchFilters = Field(
        description="Normalized candidate search filters actually applied to this search.",
    )
