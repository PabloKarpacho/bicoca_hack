from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class CandidateLanguageFilter(BaseModel):
    language_normalized: str
    min_proficiency_normalized: str | None = None


class CandidateSearchFilters(BaseModel):
    job_id: str | None = None
    source_document_id: str | None = None
    title_raw: str | None = None
    query_text: str | None = None
    query_text_responsibilities: str | None = None
    query_text_skills: str | None = None
    candidate_ids: list[str] | None = None
    current_title_normalized: list[str] | None = None
    seniority_normalized: list[str] | None = None
    min_total_experience_months: int | None = None
    max_total_experience_months: int | None = None
    location_normalized: list[str] | None = None
    remote_policies: list[str] | None = None
    employment_types: list[str] | None = None

    languages: list[CandidateLanguageFilter] | None = None
    require_all_languages: bool = False

    include_skills: list[str] | None = None
    optional_skills: list[str] | None = None
    require_all_skills: bool = False
    skill_source_type: Literal["explicit", "inferred_from_experience", "any"] = "any"

    current_or_past_titles: list[str] | None = None
    companies: list[str] | None = None
    domains: list[str] | None = None
    min_relevant_experience_months: int | None = None
    is_currently_employed_in_title: bool | None = None

    degree_normalized: list[str] | None = None
    fields_of_study: list[str] | None = None

    certifications: list[str] | None = None
    chunk_types: list[str] | None = None
    score_threshold: float = Field(default=0.75, ge=0.0, le=1.0)

    processing_status: str | None = None
    pipeline_version: str | None = None
    model_version: str | None = None
    extraction_confidence: float | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None

    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    sort_by: Literal[
        "created_at",
        "updated_at",
        "total_experience_months",
        "full_name",
    ] = "updated_at"
    sort_order: Literal["asc", "desc"] = "desc"

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
    matched_skills: list[str] = Field(default_factory=list)
    matched_languages: list[str] = Field(default_factory=list)
    matched_employment_types: list[str] = Field(default_factory=list)
    matched_degrees: list[str] = Field(default_factory=list)
    matched_fields_of_study: list[str] = Field(default_factory=list)
    education_match_status: Literal["matched", "partial", "mismatch"] | None = None
    education_match_note: str | None = None


class CandidateSearchScoreBreakdown(BaseModel):
    overall_score: float | None = None
    vector_semantic_score: float | None = None
    role_match_score: float | None = None
    skills_match_score: float | None = None
    experience_match_score: float | None = None
    language_match_score: float | None = None


class CandidateSearchResultItem(BaseModel):
    candidate_id: str
    document_id: str
    resume_download_url: str | None = None
    score: float | None = None
    match_score_percent: int | None = None
    match_score_breakdown: CandidateSearchScoreBreakdown | None = None
    full_name: str | None = None
    current_title_normalized: str | None = None
    seniority_normalized: str | None = None
    total_experience_months: int | None = None
    location_normalized: str | None = None
    remote_policies: list[str] | None = None
    matched_chunk_type: str | None = None
    matched_chunk_text_preview: str | None = None
    top_chunks: list[dict] | None = None
    match_metadata: CandidateSearchMatchMetadata | None = None


class CandidateSearchResult(BaseModel):
    total: int
    items: list[CandidateSearchResultItem]
    applied_filters: CandidateSearchFilters
