from __future__ import annotations

from typing import Any
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.common_types import (
    EducationLiteral,
    EmploymentTypeLiteral,
    ExtractedSkillSourceLiteral,
    ProficiencyLiteral,
    RemotePolicyLiteral,
    SeniorityLiteral,
)
from app.service.normalization.primitives import (
    EDUCATION_CANONICAL,
    EMPLOYMENT_TYPE_CANONICAL,
    PROFICIENCY_CANONICAL,
    REMOTE_POLICY_CANONICAL,
    SENIORITY_CANONICAL,
)


class ExtractedCandidateProfile(BaseModel):
    full_name: str | None = Field(
        default=None,
        description=(
            "Candidate full name exactly as stated in the CV header or contact section. "
            "Do not invent or expand initials."
        ),
    )
    email: str | None = Field(
        default=None,
        description="Candidate email address exactly as stated in the CV.",
    )
    phone: str | None = Field(
        default=None,
        description=(
            "Real phone number only. Do not use years, date ranges, IDs, or arbitrary "
            "digit sequences. If no clear phone number is present, use null."
        ),
    )
    location_raw: str | None = Field(
        default=None,
        description=(
            "Candidate location exactly as written in the CV, for example city, country, "
            "or city-country combination. Keep the raw text, do not normalize here."
        ),
    )
    linkedin_url: str | None = Field(
        default=None,
        description="LinkedIn profile URL if explicitly present in the CV; otherwise null.",
    )
    github_url: str | None = Field(
        default=None,
        description="GitHub profile URL if explicitly present in the CV; otherwise null.",
    )
    portfolio_url: str | None = Field(
        default=None,
        description=(
            "Personal portfolio, website, or other primary professional profile URL if "
            "explicitly present and not LinkedIn or GitHub."
        ),
    )
    headline: str | None = Field(
        default=None,
        description=(
            "Short profile headline or role label from the CV, such as 'Senior Backend "
            "Engineer'. Keep it concise and close to the source wording."
        ),
    )
    summary: str | None = Field(
        default=None,
        description=(
            "Brief factual professional summary from the CV. Keep it concise. Do not invent "
            "a summary if the CV does not provide one."
        ),
    )
    current_title_raw: str | None = Field(
        default=None,
        description=(
            "Most recent or current job title exactly as stated in the CV. Prefer the title "
            "from the current role; if no current role exists, use the most recent relevant title."
        ),
    )
    current_title_normalized: str | None = Field(
        default=None,
        description=(
            "Normalized canonical profession label for the candidate's current or most recent "
            "title. Use lowercase underscore format, for example backend_engineer or "
            "project_manager."
        ),
    )
    seniority_normalized: SeniorityLiteral | None = Field(
        default=None,
        description=(
            "Normalized seniority label inferred from the CV when clear. "
            f"Allowed values: {', '.join(SENIORITY_CANONICAL)}. Use null if unclear."
        ),
    )
    remote_policies: list[RemotePolicyLiteral] = Field(
        default_factory=list,
        description=(
            "Candidate work format preferences or explicit remote arrangement statements. "
            f"Allowed values: {', '.join(REMOTE_POLICY_CANONICAL)}. Use [] if not stated."
        ),
    )
    employment_types: list[EmploymentTypeLiteral] = Field(
        default_factory=list,
        description=(
            "Candidate preferred or explicit employment arrangements. "
            f"Allowed values: {', '.join(EMPLOYMENT_TYPE_CANONICAL)}. Use [] if not stated."
        ),
    )
    total_experience_months: int | None = Field(
        default=None,
        description=(
            "Total professional experience in months if it can be estimated reliably from the CV. "
            "Use null if not clear."
        ),
    )
    confidence: float | None = Field(
        default=None,
        description="Overall extraction confidence for the profile object, between 0 and 1.",
    )


class ExtractedLanguage(BaseModel):
    language_raw: str | None = Field(
        default=None,
        description=(
            "Language name exactly as stated in the CV, for example English or Italiano."
        ),
    )
    language_normalized: str | None = Field(
        default=None,
        description=(
            "Canonical language name when it can be inferred reliably, for example English, "
            "Italian, French, German, Spanish. Keep it human-readable."
        ),
    )
    proficiency_raw: str | None = Field(
        default=None,
        description=(
            "Original proficiency wording from the CV, for example B2, Upper-Intermediate, "
            "Full professional proficiency, or Native."
        ),
    )
    proficiency_normalized: ProficiencyLiteral | None = Field(
        default=None,
        description=(
            "Normalized language proficiency. "
            f"Allowed values: {', '.join(PROFICIENCY_CANONICAL)}. Use null if unclear."
        ),
    )
    confidence: float | None = Field(
        default=None,
        description="Extraction confidence for this language item, between 0 and 1.",
    )


class ExtractedExperience(BaseModel):
    company_name_raw: str | None = Field(
        default=None,
        description="Company or organization name exactly as stated in the CV.",
    )
    job_title_raw: str | None = Field(
        default=None,
        description="Job title exactly as written for this role in the CV.",
    )
    job_title_normalized: str | None = Field(
        default=None,
        description=(
            "Normalized canonical profession label for the role, such as backend_engineer or "
            "project_manager, when it can be inferred reliably. Use lowercase underscore format."
        ),
    )
    start_date: str | None = Field(
        default=None,
        description=(
            "Role start date in ISO format YYYY-MM-DD when possible. If only month is known, use "
            "the first day of the month. If only year is known, use January 1st."
        ),
    )
    end_date: str | None = Field(
        default=None,
        description=(
            "Role end date in ISO format YYYY-MM-DD when possible. Use null for current roles."
        ),
    )
    is_current: bool | None = Field(
        default=None,
        description="True if this is the candidate's current role; otherwise false or null if unclear.",
    )
    duration_months: int | None = Field(
        default=None,
        description="Duration of the role in months when it can be inferred reliably.",
    )
    location_raw: str | None = Field(
        default=None,
        description="Location text for the role exactly as stated in the CV.",
    )
    responsibilities_text: str | None = Field(
        default=None,
        description=(
            "Concise factual summary of the candidate's responsibilities in this role. Do not copy "
            "an entire long project section when a shorter role-focused summary is possible."
        ),
    )
    technologies_text: str | None = Field(
        default=None,
        description=(
            "Technologies, tools, frameworks, platforms, or hardware explicitly associated with "
            "this role, kept as a concise text summary."
        ),
    )
    domain_hint: str | None = Field(
        default=None,
        description=(
            "Short domain or industry hint for the role, such as fintech, healthcare, ecommerce, "
            "embedded, or robotics, when clearly supported by the CV."
        ),
    )
    confidence: float | None = Field(
        default=None,
        description="Extraction confidence for this experience item, between 0 and 1.",
    )


class ExtractedSkill(BaseModel):
    raw_skill: str | None = Field(
        default=None,
        description=(
            "Skill exactly as stated in the CV or job text. Keep it short: one word or a short "
            "phrase, not a full sentence."
        ),
    )
    normalized_skill: str | None = Field(
        default=None,
        description=(
            "Normalized canonical skill label when it can be inferred reliably, for example python, "
            "postgresql, fastapi, scrum, or jira."
        ),
    )
    skill_category: str | None = Field(
        default=None,
        description=(
            "Short category label for the skill, preferably reusing historically used labels when they "
            "fit well, such as programming_language, framework, cloud, or database."
        ),
    )
    source_type: ExtractedSkillSourceLiteral | None = Field(
        default=None,
        description=(
            "Why this skill is present. For CV extraction prefer explicit or "
            "inferred_from_experience. For vacancy extraction prefer must_have or "
            "nice_to_have. Allowed values: explicit, inferred_from_experience, "
            "must_have, nice_to_have."
        ),
    )
    confidence: float | None = Field(
        default=None,
        description="Extraction confidence for this skill item, between 0 and 1.",
    )


class ExtractedEducation(BaseModel):
    institution_raw: str | None = Field(
        default=None,
        description="University, school, or education provider name exactly as stated in the CV.",
    )
    degree_raw: str | None = Field(
        default=None,
        description="Original degree label exactly as written, for example MSc, Bachelor, or MBA.",
    )
    degree_normalized: EducationLiteral | None = Field(
        default=None,
        description=(
            "Canonical degree level only. "
            f"Allowed values: {', '.join(EDUCATION_CANONICAL)}. Use null if unclear."
        ),
    )
    field_of_study: str | None = Field(
        default=None,
        description="Field or major exactly as stated in the CV, for example Mathematics or Computer Science.",
    )
    start_date: str | None = Field(
        default=None,
        description=(
            "Education start date in ISO format YYYY-MM-DD when possible. If only year is known, "
            "use January 1st."
        ),
    )
    end_date: str | None = Field(
        default=None,
        description=(
            "Education end or graduation date in ISO format YYYY-MM-DD when possible. If only year "
            "is known, use January 1st."
        ),
    )
    confidence: float | None = Field(
        default=None,
        description="Extraction confidence for this education item, between 0 and 1.",
    )


class ExtractedCertification(BaseModel):
    certification_name_raw: str | None = Field(
        default=None,
        description=(
            "Certification or license name exactly as written in the CV or job text, for example "
            "AWS Certified Solutions Architect Associate."
        ),
    )
    certification_name_normalized: str | None = Field(
        default=None,
        description=(
            "Normalized canonical certification label when it can be inferred reliably. Use null "
            "if there is no confident normalization."
        ),
    )
    issuer: str | None = Field(
        default=None,
        description="Issuing organization exactly as stated, for example AWS, PMI, or Microsoft.",
    )
    issue_date: str | None = Field(
        default=None,
        description=(
            "Certification issue date in ISO format YYYY-MM-DD when possible. If only year is "
            "known, use January 1st."
        ),
    )
    expiry_date: str | None = Field(
        default=None,
        description=(
            "Certification expiration date in ISO format YYYY-MM-DD when possible. Use null if "
            "there is no explicit expiration date."
        ),
    )
    confidence: float | None = Field(
        default=None,
        description="Extraction confidence for this certification item, between 0 and 1.",
    )


class ExtractedJobLanguageRequirement(ExtractedLanguage):
    min_proficiency_normalized: ProficiencyLiteral | None = Field(
        default=None,
        description=(
            "Minimum required proficiency for the language requirement. "
            f"Allowed values: {', '.join(PROFICIENCY_CANONICAL)}. Use null if unclear."
        ),
    )
    required: bool = Field(
        default=True,
        description="True if the language is mandatory for the role; false if it is optional.",
    )


class ExtractedJobSearchProfile(BaseModel):
    title_raw: str | None = Field(
        default=None,
        description="Primary job title exactly as stated in the vacancy, for example Data Engineer.",
    )
    title_normalized: str | None = Field(
        default=None,
        description=(
            "Normalized canonical profession label for the role, such as data_engineer or "
            "project_manager. Use lowercase underscore format."
        ),
    )
    seniority_normalized: SeniorityLiteral | None = Field(
        default=None,
        description=(
            "Normalized seniority required for the role. "
            f"Allowed values: {', '.join(SENIORITY_CANONICAL)}. Use null if unclear."
        ),
    )
    location_raw: str | None = Field(
        default=None,
        description="Job location exactly as stated in the vacancy text.",
    )
    remote_policies: list[RemotePolicyLiteral] = Field(
        default_factory=list,
        description=(
            "Work arrangement stated in the vacancy. "
            f"Allowed values: {', '.join(REMOTE_POLICY_CANONICAL)}. Use [] if not stated."
        ),
    )
    employment_types: list[EmploymentTypeLiteral] = Field(
        default_factory=list,
        description=(
            "Employment types allowed or requested by the role. "
            f"Allowed values: {', '.join(EMPLOYMENT_TYPE_CANONICAL)}. Use [] if not stated."
        ),
    )
    min_years_experience: int | None = Field(
        default=None,
        description="Minimum years of experience required by the vacancy, when clearly stated.",
    )
    min_experience_months: int | None = Field(
        default=None,
        description=(
            "Minimum experience requirement converted to months when it can be inferred reliably."
        ),
    )
    confidence: float | None = Field(
        default=None,
        description="Overall extraction confidence for the job profile object, between 0 and 1.",
    )


class CVEntityExtractionLLMOutput(BaseModel):
    profile: ExtractedCandidateProfile = Field(
        default_factory=ExtractedCandidateProfile,
        description="Top-level candidate profile information extracted from the CV.",
    )
    languages: list[ExtractedLanguage] = Field(
        default_factory=list,
        description="All candidate languages explicitly stated or strongly implied by the CV.",
    )
    experiences: list[ExtractedExperience] = Field(
        default_factory=list,
        description="Chronological professional experience items extracted from the CV.",
    )
    skills: list[ExtractedSkill] = Field(
        default_factory=list,
        description="Candidate skills from skills sections and role evidence in the CV.",
    )
    education: list[ExtractedEducation] = Field(
        default_factory=list,
        description=(
            "All education stages from the CV. Keep sequential degrees as separate "
            "entries, even if they belong to the same university and field of study."
        ),
    )
    certifications: list[ExtractedCertification] = Field(
        default_factory=list,
        description="Candidate certifications or licenses extracted from the CV.",
    )


class JobSearchExtractionLLMOutput(BaseModel):
    profile: ExtractedJobSearchProfile = Field(
        default_factory=ExtractedJobSearchProfile,
        description="Structured top-level job requirements extracted from the vacancy text.",
    )
    languages: list[ExtractedJobLanguageRequirement] = Field(
        default_factory=list,
        description="Language requirements extracted from the vacancy, including minimum level.",
    )
    skills: list[ExtractedSkill] = Field(
        default_factory=list,
        description="Required and optional job skills extracted from the vacancy text.",
    )
    education: list[ExtractedEducation] = Field(
        default_factory=list,
        description="Education requirements extracted from the vacancy text.",
    )
    certifications: list[ExtractedCertification] = Field(
        default_factory=list,
        description="Certification requirements extracted from the vacancy text.",
    )
    domains: list[str] = Field(
        default_factory=list,
        description="Industry or business domains explicitly mentioned in the vacancy.",
    )
    responsibilities_summary: str | None = Field(
        default=None,
        description="Compact factual summary of the job responsibilities described in the vacancy.",
    )
    extraction_confidence: float | None = Field(
        default=None,
        description="Overall extraction confidence for the vacancy parsing result, between 0 and 1.",
    )

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_shape(cls, data):
        if not isinstance(data, dict):
            return data

        profile = dict(data.get("profile") or {})
        for field_name in (
            "title_raw",
            "title_normalized",
            "seniority_normalized",
            "location_raw",
            "min_years_experience",
            "min_experience_months",
        ):
            if profile.get(field_name) is None and data.get(field_name) is not None:
                profile[field_name] = data.get(field_name)

        if profile.get("employment_types") in (None, []):
            employment_type = data.get("employment_type")
            employment_types = data.get("employment_types")
            if isinstance(employment_types, list):
                profile["employment_types"] = employment_types
            elif isinstance(employment_type, list):
                profile["employment_types"] = employment_type
            elif isinstance(employment_type, str) and employment_type.strip():
                profile["employment_types"] = [employment_type]

        if profile.get("remote_policies") in (None, []):
            remote_policy = data.get("remote_policy")
            remote_policies = data.get("remote_policies")
            if isinstance(remote_policies, list):
                profile["remote_policies"] = remote_policies
            elif isinstance(remote_policy, list):
                profile["remote_policies"] = remote_policy
            elif isinstance(remote_policy, str) and remote_policy.strip():
                profile["remote_policies"] = [remote_policy]

        if "languages" not in data and data.get("required_languages") is not None:
            data["languages"] = data.get("required_languages")

        if "skills" not in data:
            skills: list[dict[str, Any]] = []
            for item in data.get("required_skills") or []:
                if isinstance(item, dict):
                    skill_item = dict(item)
                    skill_item["source_type"] = "must_have"
                    skills.append(skill_item)
            for item in data.get("optional_skills") or []:
                if isinstance(item, dict):
                    skill_item = dict(item)
                    skill_item["source_type"] = "nice_to_have"
                    skills.append(skill_item)
            data["skills"] = skills

        if "education" not in data and data.get("education_requirements") is not None:
            data["education"] = [
                {"degree_raw": item}
                for item in data.get("education_requirements") or []
                if isinstance(item, str)
            ]

        if "certifications" not in data and data.get("certification_requirements") is not None:
            data["certifications"] = [
                {"certification_name_raw": item}
                for item in data.get("certification_requirements") or []
                if isinstance(item, str)
            ]

        data["profile"] = profile
        return data


class CandidateProfileData(BaseModel):
    full_name: str | None = Field(default=None, description="Persisted candidate full name.")
    email: str | None = Field(default=None, description="Persisted candidate email address.")
    phone: str | None = Field(default=None, description="Persisted candidate phone number.")
    location_raw: str | None = Field(default=None, description="Persisted raw candidate location.")
    linkedin_url: str | None = Field(default=None, description="Persisted LinkedIn profile URL.")
    github_url: str | None = Field(default=None, description="Persisted GitHub profile URL.")
    portfolio_url: str | None = Field(
        default=None,
        description="Persisted portfolio or personal website URL.",
    )
    headline: str | None = Field(default=None, description="Persisted short profile headline.")
    summary: str | None = Field(default=None, description="Persisted candidate summary text.")
    current_title_raw: str | None = Field(
        default=None,
        description="Most recent or current job title as extracted from the CV.",
    )
    current_title_normalized: str | None = Field(
        default=None,
        description="Normalized canonical label for the candidate's current title.",
    )
    seniority_normalized: SeniorityLiteral | None = Field(
        default=None,
        description="Normalized canonical seniority for the candidate profile.",
    )
    remote_policies: list[RemotePolicyLiteral] | None = Field(
        default=None,
        description="Persisted remote work preferences or arrangements when available.",
    )
    employment_types: list[EmploymentTypeLiteral] | None = Field(
        default=None,
        description="Persisted employment type preferences or constraints when available.",
    )
    total_experience_months: int | None = Field(
        default=None,
        description="Persisted total candidate experience in months.",
    )
    extraction_confidence: float | None = Field(
        default=None,
        description="Overall extraction confidence stored for the candidate profile.",
    )


class CandidateLanguageData(BaseModel):
    language_raw: str | None = Field(default=None, description="Language label as originally extracted.")
    language_normalized: str | None = Field(
        default=None,
        description="Normalized human-readable language name.",
    )
    proficiency_raw: str | None = Field(
        default=None,
        description="Original proficiency wording from the source document.",
    )
    proficiency_normalized: ProficiencyLiteral | None = Field(
        default=None,
        description="Normalized canonical proficiency level.",
    )
    confidence: float | None = Field(
        default=None,
        description="Extraction confidence for this persisted language item.",
    )


class CandidateExperienceData(BaseModel):
    position_order: int = Field(description="Stable ordering of the experience item within the document.")
    company_name_raw: str | None = Field(default=None, description="Persisted raw company or organization name.")
    job_title_raw: str | None = Field(default=None, description="Persisted raw job title.")
    job_title_normalized: str | None = Field(
        default=None,
        description="Normalized canonical label for the role title.",
    )
    start_date: date | None = Field(default=None, description="Persisted role start date.")
    end_date: date | None = Field(default=None, description="Persisted role end date, if any.")
    is_current: bool = Field(default=False, description="Whether the role is current.")
    duration_months: int | None = Field(default=None, description="Persisted duration of the role in months.")
    location_raw: str | None = Field(default=None, description="Persisted raw location for the role.")
    responsibilities_text: str | None = Field(
        default=None,
        description="Persisted concise summary of responsibilities for the role.",
    )
    technologies_text: str | None = Field(
        default=None,
        description="Persisted concise summary of technologies or tools used in the role.",
    )
    domain_hint: str | None = Field(
        default=None,
        description="Persisted short industry or domain hint for the role.",
    )
    confidence: float | None = Field(
        default=None,
        description="Extraction confidence for this persisted experience item.",
    )


class CandidateSkillData(BaseModel):
    raw_skill: str | None = Field(default=None, description="Skill as originally extracted from the source.")
    normalized_skill: str | None = Field(
        default=None,
        description="Normalized canonical skill label stored for downstream search.",
    )
    skill_category: str | None = Field(
        default=None,
        description="Persisted category label for the skill.",
    )
    source_type: ExtractedSkillSourceLiteral | None = Field(
        default=None,
        description="Why the skill is present in the extracted result.",
    )
    confidence: float | None = Field(
        default=None,
        description="Extraction confidence for this persisted skill item.",
    )
    normalization_source: str | None = Field(
        default=None,
        description="Provider or strategy that produced the skill normalization.",
    )
    normalization_external_id: int | None = Field(
        default=None,
        description="External provider identifier used during normalization, when available.",
    )
    normalization_status: str | None = Field(
        default=None,
        description="Normalization status captured for the skill.",
    )
    normalization_confidence: float | None = Field(
        default=None,
        description="Confidence of the normalization step for the skill.",
    )
    normalization_metadata: dict[str, Any] | None = Field(
        default=None,
        description="Additional normalization metadata captured for the skill.",
    )


class CandidateEducationData(BaseModel):
    position_order: int = Field(description="Stable ordering of the education item within the document.")
    institution_raw: str | None = Field(default=None, description="Persisted raw institution name.")
    degree_raw: str | None = Field(default=None, description="Persisted raw degree label.")
    degree_normalized: EducationLiteral | None = Field(
        default=None,
        description="Normalized canonical degree level.",
    )
    field_of_study: str | None = Field(default=None, description="Persisted field or major.")
    start_date: date | None = Field(default=None, description="Persisted education start date.")
    end_date: date | None = Field(default=None, description="Persisted education end or graduation date.")
    confidence: float | None = Field(
        default=None,
        description="Extraction confidence for this persisted education item.",
    )


class CandidateCertificationData(BaseModel):
    certification_name_raw: str | None = Field(
        default=None,
        description="Persisted raw certification or license name.",
    )
    certification_name_normalized: str | None = Field(
        default=None,
        description="Normalized certification label when available.",
    )
    issuer: str | None = Field(default=None, description="Persisted certification issuer.")
    issue_date: date | None = Field(default=None, description="Persisted certification issue date.")
    expiry_date: date | None = Field(default=None, description="Persisted certification expiry date.")
    confidence: float | None = Field(
        default=None,
        description="Extraction confidence for this persisted certification item.",
    )


class CandidateEntitiesData(BaseModel):
    profile: CandidateProfileData = Field(description="Persisted candidate profile payload.")
    languages: list[CandidateLanguageData] = Field(description="Persisted candidate languages.")
    experiences: list[CandidateExperienceData] = Field(description="Persisted candidate experience items.")
    skills: list[CandidateSkillData] = Field(description="Persisted candidate skills.")
    education: list[CandidateEducationData] = Field(description="Persisted candidate education items.")
    certifications: list[CandidateCertificationData] = Field(
        description="Persisted candidate certifications."
    )


class ProcessingRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    processing_run_id: str = Field(description="Unique processing run identifier.")
    document_id: str = Field(description="Document identifier associated with the processing run.")
    candidate_id: str | None = Field(default=None, description="Candidate identifier when available.")
    processing_stage: str = Field(description="Pipeline stage executed by the processing run.")
    status: str = Field(description="Current status of the processing run.")
    pipeline_version: str = Field(description="Pipeline version used for the processing run.")
    model_version: str | None = Field(default=None, description="LLM or model version used, when available.")
    extraction_confidence: float | None = Field(
        default=None,
        description="Overall extraction confidence recorded for the run.",
    )
    error_message: str | None = Field(default=None, description="Error message if the run failed.")
    started_at: datetime | None = Field(default=None, description="Timestamp when processing started.")
    completed_at: datetime | None = Field(default=None, description="Timestamp when processing completed.")
    created_at: datetime = Field(description="Creation timestamp for the processing run record.")
    updated_at: datetime = Field(description="Last update timestamp for the processing run record.")


class EntityExtractionRunResponse(BaseModel):
    document_id: str = Field(description="Document identifier for the extraction run.")
    candidate_id: str | None = Field(default=None, description="Candidate identifier when available.")
    status: str = Field(description="Current extraction status.")
    pipeline_version: str = Field(description="Pipeline version used for extraction.")
    model_version: str | None = Field(default=None, description="Model version used for extraction.")
    extraction_confidence: float | None = Field(
        default=None,
        description="Overall extraction confidence returned for the run.",
    )


class CandidateEntitiesResponse(BaseModel):
    document_id: str = Field(description="Document identifier for the extracted candidate entities.")
    candidate_id: str | None = Field(default=None, description="Candidate identifier when available.")
    processing_run: ProcessingRunResponse | None = Field(
        default=None,
        description="Latest processing run metadata associated with the document.",
    )
    profile: CandidateProfileData | None = Field(
        default=None,
        description="Persisted candidate profile data for the document.",
    )
    languages: list[CandidateLanguageData] = Field(description="Persisted candidate languages.")
    experiences: list[CandidateExperienceData] = Field(description="Persisted candidate experience items.")
    skills: list[CandidateSkillData] = Field(description="Persisted candidate skills.")
    education: list[CandidateEducationData] = Field(description="Persisted candidate education items.")
    certifications: list[CandidateCertificationData] = Field(
        description="Persisted candidate certifications."
    )
