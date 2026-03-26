from __future__ import annotations

import re
from typing import TYPE_CHECKING, Iterable

from app.config.enums.normalization_class import NormalizationClass
from app.models.entity_extraction import (
    CVEntityExtractionLLMOutput,
    CandidateCertificationData,
    CandidateEducationData,
    CandidateEntitiesData,
    CandidateExperienceData,
    CandidateLanguageData,
    CandidateProfileData,
    CandidateSkillData,
)
from app.service.normalization.primitives import (
    SKILL_CATEGORIES,
    compute_duration_months,
    extract_employment_types,
    extract_remote_policies,
    infer_seniority,
    normalize_degree,
    normalize_job_title,
    normalize_language_level,
    parse_partial_date,
)
from app.service.normalization.skill_utils import (
    normalize_skill_value,
    normalize_skill_with_hh,
    registry_skill_normalization_metadata,
    registry_skill_normalization_source,
    registry_skill_normalization_status,
    resolve_normalized_skill,
    skill_normalization_metadata,
    skill_normalization_source,
    skill_normalization_status,
)
from app.service.skills.hh_skill_normalizer import HHSkillNormalizerService

if TYPE_CHECKING:
    from app.service.normalization.service import EntityNormalizationService

EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.\w+")
URL_RE = re.compile(r"https?://[^\s)>,]+")


async def normalize_entities(
    *,
    raw_text: str,
    extracted: CVEntityExtractionLLMOutput,
    candidate_full_name: str | None = None,
    candidate_email: str | None = None,
    normalization_service: EntityNormalizationService | None = None,
    skill_normalizer: HHSkillNormalizerService | None = None,
) -> CandidateEntitiesData:
    languages = [
        await _normalize_language(item, normalization_service=normalization_service)
        for item in extracted.languages
    ]
    experiences = [
        await _normalize_experience(
            item,
            index=index + 1,
            normalization_service=normalization_service,
        )
        for index, item in enumerate(extracted.experiences)
    ]
    skills = await _normalize_skills(
        extracted.skills,
        experiences,
        normalization_service=normalization_service,
        skill_normalizer=skill_normalizer,
    )
    education = [
        await _normalize_education(
            item,
            index=index + 1,
            normalization_service=normalization_service,
        )
        for index, item in enumerate(extracted.education)
    ]
    certifications = [_normalize_certification(item) for item in extracted.certifications]
    total_experience_months = _compute_total_experience_months(experiences)
    profile = await _normalize_profile(
        raw_text=raw_text,
        extracted_profile=extracted.profile,
        candidate_full_name=candidate_full_name,
        candidate_email=candidate_email,
        experiences=experiences,
        total_experience_months=total_experience_months,
        normalization_service=normalization_service,
    )
    return CandidateEntitiesData(
        profile=profile,
        languages=[item for item in languages if item.language_normalized or item.language_raw],
        experiences=[
            item for item in experiences if item.company_name_raw or item.job_title_raw
        ],
        skills=[item for item in skills if item.normalized_skill or item.raw_skill],
        education=[item for item in education if item.institution_raw or item.degree_raw],
        certifications=[
            item
            for item in certifications
            if item.certification_name_normalized or item.certification_name_raw
        ],
    )


def compute_overall_confidence(entities: CandidateEntitiesData) -> float | None:
    values = list(
        _iter_confidences(
            [
                entities.profile.extraction_confidence,
                *(item.confidence for item in entities.languages),
                *(item.confidence for item in entities.experiences),
                *(item.confidence for item in entities.skills),
                *(item.confidence for item in entities.education),
                *(item.confidence for item in entities.certifications),
            ]
        )
    )
    if not values:
        return None
    return round(sum(values) / len(values), 4)


async def _normalize_profile(
    *,
    raw_text: str,
    extracted_profile,
    candidate_full_name: str | None,
    candidate_email: str | None,
    experiences: list[CandidateExperienceData],
    total_experience_months: int | None,
    normalization_service: EntityNormalizationService | None,
) -> CandidateProfileData:
    urls = URL_RE.findall(raw_text)
    email = extracted_profile.email or candidate_email or _first_match(EMAIL_RE, raw_text)
    phone = _clean_text(extracted_profile.phone)
    linkedin_url = extracted_profile.linkedin_url or _first_url(urls, "linkedin.com")
    github_url = extracted_profile.github_url or _first_url(urls, "github.com")
    portfolio_url = extracted_profile.portfolio_url or _first_non_profile_url(urls)
    current_title_raw = extracted_profile.current_title_raw or (
        experiences[0].job_title_raw if experiences else None
    )
    current_title_normalized = extracted_profile.current_title_normalized or normalize_job_title(
        current_title_raw
    )
    if normalization_service is not None and current_title_raw:
        title_result = await normalization_service.normalize(
            original_value=current_title_raw,
            normalization_class=NormalizationClass.PROFESSIONS,
        )
        current_title_normalized = title_result.normalized_value or current_title_normalized
    seniority_normalized = extracted_profile.seniority_normalized or infer_seniority(
        current_title_raw or extracted_profile.headline
    )
    if normalization_service is not None:
        seniority_result = await normalization_service.normalize(
            original_value=seniority_normalized or current_title_raw or extracted_profile.headline,
            normalization_class=NormalizationClass.SENIORITY_LEVELS,
        )
        seniority_normalized = seniority_result.normalized_value or seniority_normalized
    remote_policies = extract_remote_policies(extracted_profile.remote_policies)
    if normalization_service is not None and remote_policies:
        normalized_remote_policies = []
        for value in remote_policies:
            result = await normalization_service.normalize(
                original_value=value,
                normalization_class=NormalizationClass.REMOTE_POLICY,
            )
            if result.normalized_value and result.normalized_value not in normalized_remote_policies:
                normalized_remote_policies.append(result.normalized_value)
        remote_policies = normalized_remote_policies or remote_policies
    employment_types = extract_employment_types(extracted_profile.employment_types)
    if normalization_service is not None and employment_types:
        normalized_employment_types = []
        for value in employment_types:
            result = await normalization_service.normalize(
                original_value=value,
                normalization_class=NormalizationClass.EMPLOYMENT_TYPE,
            )
            if (
                result.normalized_value
                and result.normalized_value not in normalized_employment_types
            ):
                normalized_employment_types.append(result.normalized_value)
        employment_types = normalized_employment_types or employment_types
    full_name = extracted_profile.full_name or candidate_full_name or _first_line(raw_text)
    return CandidateProfileData(
        full_name=full_name,
        email=email,
        phone=phone,
        location_raw=extracted_profile.location_raw,
        linkedin_url=linkedin_url,
        github_url=github_url,
        portfolio_url=portfolio_url,
        headline=extracted_profile.headline,
        summary=extracted_profile.summary,
        current_title_raw=current_title_raw,
        current_title_normalized=current_title_normalized,
        seniority_normalized=seniority_normalized,
        remote_policies=remote_policies,
        employment_types=employment_types,
        total_experience_months=extracted_profile.total_experience_months
        or total_experience_months,
        extraction_confidence=extracted_profile.confidence,
    )


async def _normalize_language(item, *, normalization_service: EntityNormalizationService | None) -> CandidateLanguageData:
    raw = _clean_text(item.language_raw)
    proficiency_raw = _clean_text(item.proficiency_raw)
    normalized = item.language_normalized or raw
    normalized_language = _title_or_none(normalized)
    normalized_proficiency = normalize_language_level(item.proficiency_normalized or proficiency_raw)
    if normalization_service is not None and normalized:
        language_result = await normalization_service.normalize(
            original_value=normalized,
            normalization_class=NormalizationClass.LANGUAGES,
        )
        normalized_language = language_result.normalized_value or normalized_language
    if normalization_service is not None and (item.proficiency_normalized or proficiency_raw):
        proficiency_result = await normalization_service.normalize(
            original_value=item.proficiency_normalized or proficiency_raw,
            normalization_class=NormalizationClass.PROFICIENCY_LEVELS,
        )
        normalized_proficiency = proficiency_result.normalized_value or normalized_proficiency
    return CandidateLanguageData(
        language_raw=raw,
        language_normalized=normalized_language,
        proficiency_raw=proficiency_raw,
        proficiency_normalized=normalized_proficiency,
        confidence=item.confidence,
    )


async def _normalize_experience(
    item,
    *,
    index: int,
    normalization_service: EntityNormalizationService | None,
) -> CandidateExperienceData:
    start_date = parse_partial_date(item.start_date)
    end_date = parse_partial_date(item.end_date)
    is_current = bool(item.is_current) or _looks_current(item.end_date)
    normalized_title = item.job_title_normalized or normalize_job_title(item.job_title_raw)
    if normalization_service is not None and item.job_title_raw:
        title_result = await normalization_service.normalize(
            original_value=item.job_title_raw,
            normalization_class=NormalizationClass.PROFESSIONS,
        )
        normalized_title = title_result.normalized_value or normalized_title
    duration = item.duration_months or compute_duration_months(
        start_date=start_date,
        end_date=end_date,
        is_current=is_current,
    )
    return CandidateExperienceData(
        position_order=index,
        company_name_raw=_clean_text(item.company_name_raw),
        job_title_raw=_clean_text(item.job_title_raw),
        job_title_normalized=normalized_title,
        start_date=start_date,
        end_date=None if is_current else end_date,
        is_current=is_current,
        duration_months=duration,
        location_raw=_clean_text(item.location_raw),
        responsibilities_text=_clean_text(item.responsibilities_text),
        technologies_text=_clean_text(item.technologies_text),
        domain_hint=_clean_text(item.domain_hint),
        confidence=item.confidence,
    )


async def _normalize_skills(
    extracted_skills,
    experiences: list[CandidateExperienceData],
    *,
    normalization_service: EntityNormalizationService | None,
    skill_normalizer: HHSkillNormalizerService | None,
) -> list[CandidateSkillData]:
    items: list[CandidateSkillData] = []
    seen: set[tuple[str, str]] = set()

    for item in extracted_skills:
        normalization_result = await normalize_skill_with_hh(
            item.raw_skill or item.normalized_skill,
            skill_normalizer=skill_normalizer,
        )
        normalized = resolve_normalized_skill(
            fallback_value=item.normalized_skill or item.raw_skill,
            normalization_result=normalization_result,
        )
        registry_result = None
        if normalization_service is not None and (item.raw_skill or item.normalized_skill):
            registry_result = await normalization_service.normalize(
                original_value=item.raw_skill or item.normalized_skill,
                normalization_class=NormalizationClass.SKILLS,
            )
            normalized = registry_result.normalized_value or normalized
        key = (normalized or "", item.source_type or "explicit")
        if normalized and key in seen:
            continue
        if normalized:
            seen.add(key)
        items.append(
            CandidateSkillData(
                raw_skill=_clean_text(item.raw_skill),
                normalized_skill=normalized,
                skill_category=item.skill_category or SKILL_CATEGORIES.get(normalized or ""),
                source_type=item.source_type or "explicit",
                confidence=item.confidence,
                normalization_source=(
                    registry_skill_normalization_source(registry_result)
                    if registry_result is not None
                    else skill_normalization_source(normalization_result=normalization_result)
                ),
                normalization_external_id=(
                    (registry_result.metadata or {}).get("external_id")
                    if registry_result is not None and registry_result.metadata
                    else (
                        normalization_result.normalized_skill_external_id
                        if normalization_result
                        else None
                    )
                ),
                normalization_status=(
                    registry_skill_normalization_status(registry_result)
                    if registry_result is not None
                    else skill_normalization_status(normalization_result=normalization_result)
                ),
                normalization_confidence=(
                    registry_result.confidence
                    if registry_result is not None
                    else (normalization_result.confidence if normalization_result else None)
                ),
                normalization_metadata=(
                    registry_skill_normalization_metadata(registry_result)
                    if registry_result is not None
                    else skill_normalization_metadata(normalization_result=normalization_result)
                ),
            )
        )

    for experience in experiences:
        for raw_skill in _split_technologies(experience.technologies_text):
            normalization_result = await normalize_skill_with_hh(
                raw_skill,
                skill_normalizer=skill_normalizer,
            )
            normalized = resolve_normalized_skill(
                fallback_value=raw_skill,
                normalization_result=normalization_result,
            )
            registry_result = None
            if normalization_service is not None:
                registry_result = await normalization_service.normalize(
                    original_value=raw_skill,
                    normalization_class=NormalizationClass.SKILLS,
                )
                normalized = registry_result.normalized_value or normalized
            key = (normalized or "", "inferred_from_experience")
            if not normalized or key in seen:
                continue
            seen.add(key)
            items.append(
                CandidateSkillData(
                    raw_skill=raw_skill,
                    normalized_skill=normalized,
                    skill_category=SKILL_CATEGORIES.get(normalized),
                    source_type="inferred_from_experience",
                    confidence=0.55,
                    normalization_source=(
                        registry_skill_normalization_source(registry_result)
                        if registry_result is not None
                        else skill_normalization_source(normalization_result=normalization_result)
                    ),
                    normalization_external_id=(
                        (registry_result.metadata or {}).get("external_id")
                        if registry_result is not None and registry_result.metadata
                        else (
                            normalization_result.normalized_skill_external_id
                            if normalization_result
                            else None
                        )
                    ),
                    normalization_status=(
                        registry_skill_normalization_status(registry_result)
                        if registry_result is not None
                        else skill_normalization_status(normalization_result=normalization_result)
                    ),
                    normalization_confidence=(
                        registry_result.confidence
                        if registry_result is not None
                        else (normalization_result.confidence if normalization_result else None)
                    ),
                    normalization_metadata=(
                        registry_skill_normalization_metadata(registry_result)
                        if registry_result is not None
                        else skill_normalization_metadata(normalization_result=normalization_result)
                    ),
                )
            )

    return items


async def _normalize_education(
    item,
    *,
    index: int,
    normalization_service: EntityNormalizationService | None,
) -> CandidateEducationData:
    raw_degree = _clean_text(item.degree_raw)
    degree_normalized = item.degree_normalized or normalize_degree(raw_degree)
    if normalization_service is not None and raw_degree:
        degree_result = await normalization_service.normalize(
            original_value=raw_degree,
            normalization_class=NormalizationClass.EDUCATION,
        )
        degree_normalized = degree_result.normalized_value or degree_normalized
    return CandidateEducationData(
        position_order=index,
        institution_raw=_clean_text(item.institution_raw),
        degree_raw=raw_degree,
        degree_normalized=degree_normalized,
        field_of_study=_clean_text(item.field_of_study),
        start_date=parse_partial_date(item.start_date),
        end_date=parse_partial_date(item.end_date),
        confidence=item.confidence,
    )


def _normalize_certification(item) -> CandidateCertificationData:
    raw_name = _clean_text(item.certification_name_raw)
    return CandidateCertificationData(
        certification_name_raw=raw_name,
        certification_name_normalized=item.certification_name_normalized or _title_or_none(raw_name),
        issuer=_clean_text(item.issuer),
        issue_date=parse_partial_date(item.issue_date),
        expiry_date=parse_partial_date(item.expiry_date),
        confidence=item.confidence,
    )


def _compute_total_experience_months(experiences: list[CandidateExperienceData]) -> int | None:
    values = [item.duration_months for item in experiences if item.duration_months is not None]
    if not values:
        return None
    return sum(values)


def _looks_current(value: str | None) -> bool:
    if not value:
        return False
    return value.strip().lower() in {"present", "current", "now", "oggi", "attuale"}


def _split_technologies(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in re.split(r"[,/|;]", value) if item and item.strip()]


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", value).strip()
    return cleaned or None


def _first_match(pattern: re.Pattern[str], raw_text: str) -> str | None:
    match = pattern.search(raw_text)
    return match.group(0).strip() if match else None


def _first_url(urls: list[str], domain_fragment: str) -> str | None:
    for url in urls:
        if domain_fragment in url.lower():
            return url
    return None


def _first_non_profile_url(urls: list[str]) -> str | None:
    for url in urls:
        lowered = url.lower()
        if "linkedin.com" in lowered or "github.com" in lowered:
            continue
        return url
    return None


def _first_line(raw_text: str) -> str | None:
    for line in raw_text.splitlines():
        cleaned = line.strip()
        if cleaned and "@" not in cleaned and len(cleaned.split()) <= 6:
            return cleaned
    return None


def _title_or_none(value: str | None) -> str | None:
    return value.title() if value else None


def _iter_confidences(values: Iterable[float | None]) -> Iterable[float]:
    for value in values:
        if value is None:
            continue
        yield value
