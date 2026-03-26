from __future__ import annotations

import json
import re
from dataclasses import dataclass

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.enums.normalization_class import NormalizationClass
from app.config.enums.normalization_status import NormalizationStatus
from app.models.normalization import EntityNormalizationResult
from app.service.normalization.primitives import (
    DEGREE_SYNONYMS,
    EDUCATION_CANONICAL,
    EMPLOYMENT_TYPE_CANONICAL,
    EMPLOYMENT_TYPE_MAP,
    JOB_TITLE_CLUSTERS,
    LANGUAGE_LEVELS,
    LANGUAGE_NAME_SYNONYMS,
    PROFICIENCY_CANONICAL,
    REMOTE_POLICY_CANONICAL,
    REMOTE_POLICY_MAP,
    SENIORITY_CANONICAL,
    SKILL_CATEGORIES,
    infer_seniority,
    normalize_degree,
    normalize_employment_type,
    normalize_job_title,
    normalize_language_level,
    normalize_language_name,
    normalize_remote_policy,
    normalize_skill_name,
)
from app.service.normalization.agent_client import NormalizationAgentClient
from app.service.skills.hh_skill_normalizer import HHSkillNormalizerService
from app.service.work.hh_work_normalizer import HHWorkNormalizerService
from database.postgres.crud.cv import EntityNormalizationRepository

PIPELINE_VERSION = "entity_normalization_mvp_v1"

PROFICIENCY_CANONICAL_WITH_UNKNOWN = [*PROFICIENCY_CANONICAL, "unknown"]
SENIORITY_CANONICAL_WITH_UNKNOWN = [*SENIORITY_CANONICAL, "unknown"]
LANGUAGE_CANONICAL = [
    "English",
    "Italian",
    "French",
    "German",
    "Spanish",
    "Portuguese",
    "Polish",
    "Russian",
    "Ukrainian",
]
SKILL_CANONICAL = sorted(SKILL_CATEGORIES.keys())
PROFESSION_CANONICAL = sorted(set(JOB_TITLE_CLUSTERS.values()))
REMOTE_POLICY_CANONICAL_LIST = list(REMOTE_POLICY_CANONICAL)
EMPLOYMENT_TYPE_CANONICAL_LIST = list(EMPLOYMENT_TYPE_CANONICAL)
EDUCATION_CANONICAL_LIST = list(EDUCATION_CANONICAL)
CITY_SYNONYMS = {
    "milan": "Milan",
    "milano": "Milan",
    "rome": "Rome",
    "roma": "Rome",
    "berlin": "Berlin",
    "paris": "Paris",
    "london": "London",
    "warsaw": "Warsaw",
}
COUNTRY_SYNONYMS = {
    "italy": "Italy",
    "italia": "Italy",
    "germany": "Germany",
    "deutschland": "Germany",
    "france": "France",
    "spain": "Spain",
    "united kingdom": "United Kingdom",
    "uk": "United Kingdom",
    "usa": "United States",
    "united states": "United States",
}


@dataclass
class EntityNormalizationService:
    """Registry-first generalized normalization service for all supported classes."""

    session: AsyncSession
    agent_client: NormalizationAgentClient | None = None
    skill_normalizer: HHSkillNormalizerService | None = None
    work_normalizer: HHWorkNormalizerService | None = None

    def __post_init__(self) -> None:
        self.registry = EntityNormalizationRepository(self.session)
        self.agent_client = self.agent_client or NormalizationAgentClient()
        self.skill_normalizer = self.skill_normalizer or HHSkillNormalizerService()
        self.work_normalizer = self.work_normalizer or HHWorkNormalizerService()

    async def normalize(
        self,
        *,
        original_value: str | None,
        normalization_class: NormalizationClass,
        context_metadata: dict | None = None,
    ) -> EntityNormalizationResult:
        logger.info(
            "Entity normalization requested: class={normalization_class}, original_value={original_value}",
            normalization_class=normalization_class.value,
            original_value=original_value,
        )
        cleaned = _clean_value(original_value)
        if cleaned is None:
            return EntityNormalizationResult(
                original_value=original_value or "",
                normalization_class=normalization_class,
                normalized_value=None,
                normalized_value_canonical=None,
                status=NormalizationStatus.FAILED,
                provider="local",
                confidence=0.0,
                was_cache_hit=False,
                pipeline_version=PIPELINE_VERSION,
                metadata={"reason": "empty_input"},
            )

        lookup = build_lookup_value(cleaned)
        cached = await self.registry.get_by_class_and_original_lookup(
            normalization_class,
            lookup,
        )
        if cached is not None:
            logger.info(
                "Entity normalization cache hit: class={normalization_class}, original_value={original_value}, normalized_value={normalized_value}",
                normalization_class=normalization_class.value,
                original_value=cleaned,
                normalized_value=cached.normalized_value,
            )
            return EntityNormalizationResult(
                original_value=cleaned,
                normalization_class=normalization_class,
                normalized_value=cached.normalized_value,
                normalized_value_canonical=cached.normalized_value_canonical,
                status=NormalizationStatus(cached.normalization_status),
                provider=cached.provider,
                confidence=cached.confidence,
                was_cache_hit=True,
                model_version=cached.model_version,
                pipeline_version=cached.pipeline_version,
                metadata=_loads_metadata(cached.metadata_json),
            )

        canonical_values = await self.list_canonical_values(normalization_class)
        logger.info(
            "Entity normalization cache miss: class={normalization_class}, original_value={original_value}, canonical_count={canonical_count}",
            normalization_class=normalization_class.value,
            original_value=cleaned,
            canonical_count=len(canonical_values),
        )
        result = await self._dispatch(
            original_value=cleaned,
            normalization_class=normalization_class,
            canonical_values=canonical_values,
            context_metadata=context_metadata or {},
        )
        await self.registry.upsert_normalization(
            normalization_class=normalization_class,
            original_value=cleaned,
            original_value_lookup=lookup,
            normalized_value=result.normalized_value,
            normalized_value_canonical=result.normalized_value_canonical,
            normalization_status=result.status,
            confidence=result.confidence,
            provider=result.provider,
            model_version=result.model_version,
            pipeline_version=result.pipeline_version,
            metadata_json=json.dumps(result.metadata, ensure_ascii=False)
            if result.metadata is not None
            else None,
        )
        logger.info(
            "Entity normalization persisted: class={normalization_class}, original_value={original_value}, normalized_value={normalized_value}, status={status}, provider={provider}",
            normalization_class=normalization_class.value,
            original_value=cleaned,
            normalized_value=result.normalized_value,
            status=result.status.value,
            provider=result.provider,
        )
        return result

    async def list_canonical_values(
        self,
        normalization_class: NormalizationClass,
    ) -> list[str]:
        registry_values = await self.registry.list_canonical_values_by_class(
            normalization_class
        )
        seeded = _seed_canonical_values(normalization_class)
        return list(dict.fromkeys([*registry_values, *seeded]))

    async def _dispatch(
        self,
        *,
        original_value: str,
        normalization_class: NormalizationClass,
        canonical_values: list[str],
        context_metadata: dict,
    ) -> EntityNormalizationResult:
        if normalization_class == NormalizationClass.SKILLS:
            return await self._normalize_skill(
                original_value=original_value,
                canonical_values=canonical_values,
            )
        if normalization_class == NormalizationClass.PROFESSIONS:
            return await self._normalize_profession(
                original_value=original_value,
                canonical_values=canonical_values,
            )
        deterministic = _deterministic_normalize(
            original_value=original_value,
            normalization_class=normalization_class,
            canonical_values=canonical_values,
        )
        if deterministic is not None:
            return EntityNormalizationResult(
                original_value=original_value,
                normalization_class=normalization_class,
                normalized_value=deterministic,
                normalized_value_canonical=deterministic,
                status=NormalizationStatus.NORMALIZED,
                provider="legacy_rule",
                confidence=0.9,
                was_cache_hit=False,
                pipeline_version=PIPELINE_VERSION,
                metadata={
                    "matched_existing_canonical": deterministic in canonical_values,
                    "context": context_metadata or None,
                },
            )
        logger.info(
            "Entity normalization agent dispatch: class={normalization_class}, original_value={original_value}",
            normalization_class=normalization_class.value,
            original_value=original_value,
        )
        agent_result = await self.agent_client.normalize(
            normalization_class=normalization_class,
            original_value=original_value,
            canonical_values=canonical_values,
        )
        normalized_value = (
            _clean_value(agent_result.normalized_value)
            if agent_result.normalized_value
            else None
        )
        return EntityNormalizationResult(
            original_value=original_value,
            normalization_class=normalization_class,
            normalized_value=normalized_value,
            normalized_value_canonical=normalized_value,
            status=agent_result.status,
            provider="agent",
            confidence=agent_result.confidence,
            was_cache_hit=False,
            model_version=self.agent_client.model,
            pipeline_version=PIPELINE_VERSION,
            metadata={
                "matched_existing_canonical": agent_result.matched_existing_canonical,
                "rationale_short": agent_result.rationale_short,
                "canonical_count": len(canonical_values),
                "context": context_metadata or None,
            },
        )

    async def _normalize_skill(
        self,
        *,
        original_value: str,
        canonical_values: list[str],
    ) -> EntityNormalizationResult:
        local_candidate = normalize_skill_name(original_value)
        hh_result = await self.skill_normalizer.normalize_skill(original_value)
        if hh_result.normalized_skill_text:
            normalized = normalize_skill_name(hh_result.normalized_skill_text)
            return EntityNormalizationResult(
                original_value=original_value,
                normalization_class=NormalizationClass.SKILLS,
                normalized_value=normalized,
                normalized_value_canonical=normalized,
                status=NormalizationStatus.NORMALIZED,
                provider="hh",
                confidence=hh_result.confidence,
                was_cache_hit=False,
                pipeline_version=PIPELINE_VERSION,
                metadata={
                    "external_id": hh_result.normalized_skill_external_id,
                    "match_type": hh_result.match_type,
                    "alternatives": [item.model_dump() for item in hh_result.alternatives],
                    "matched_existing_canonical": normalized in canonical_values,
                },
            )

        if local_candidate and (
            not canonical_values or local_candidate in canonical_values
        ):
            return EntityNormalizationResult(
                original_value=original_value,
                normalization_class=NormalizationClass.SKILLS,
                normalized_value=local_candidate,
                normalized_value_canonical=local_candidate,
                status=NormalizationStatus.NORMALIZED,
                provider="legacy_rule",
                confidence=0.9,
                was_cache_hit=False,
                pipeline_version=PIPELINE_VERSION,
                metadata={
                    "matched_existing_canonical": local_candidate in canonical_values,
                    "hh_match_type": hh_result.match_type,
                    "hh_error": hh_result.error,
                },
            )

        logger.info(
            "Entity normalization skill fallback to agent: original_value={original_value}",
            original_value=original_value,
        )
        agent_result = await self.agent_client.normalize(
            normalization_class=NormalizationClass.SKILLS,
            original_value=original_value,
            canonical_values=canonical_values,
        )
        normalized = (
            normalize_skill_name(agent_result.normalized_value)
            if agent_result.normalized_value
            else None
        )
        return EntityNormalizationResult(
            original_value=original_value,
            normalization_class=NormalizationClass.SKILLS,
            normalized_value=normalized,
            normalized_value_canonical=normalized,
            status=agent_result.status,
            provider="agent",
            confidence=agent_result.confidence,
            was_cache_hit=False,
            model_version=self.agent_client.model,
            pipeline_version=PIPELINE_VERSION,
            metadata={
                "matched_existing_canonical": agent_result.matched_existing_canonical,
                "rationale_short": agent_result.rationale_short,
                "hh_match_type": hh_result.match_type,
                "hh_error": hh_result.error,
            },
        )

    async def _normalize_profession(
        self,
        *,
        original_value: str,
        canonical_values: list[str],
    ) -> EntityNormalizationResult:
        local_candidate = normalize_job_title(original_value)
        hh_result = await self.work_normalizer.normalize_work(original_value)
        if hh_result.normalized_work_text:
            normalized = normalize_job_title(hh_result.normalized_work_text)
            return EntityNormalizationResult(
                original_value=original_value,
                normalization_class=NormalizationClass.PROFESSIONS,
                normalized_value=normalized,
                normalized_value_canonical=normalized,
                status=NormalizationStatus.NORMALIZED,
                provider="hh",
                confidence=hh_result.confidence,
                was_cache_hit=False,
                pipeline_version=PIPELINE_VERSION,
                metadata={
                    "external_id": hh_result.normalized_work_external_id,
                    "match_type": hh_result.match_type,
                    "alternatives": [item.model_dump() for item in hh_result.alternatives],
                    "matched_existing_canonical": normalized in canonical_values,
                },
            )

        if local_candidate and (
            not canonical_values or local_candidate in canonical_values
        ):
            return EntityNormalizationResult(
                original_value=original_value,
                normalization_class=NormalizationClass.PROFESSIONS,
                normalized_value=local_candidate,
                normalized_value_canonical=local_candidate,
                status=NormalizationStatus.NORMALIZED,
                provider="legacy_rule",
                confidence=0.9,
                was_cache_hit=False,
                pipeline_version=PIPELINE_VERSION,
                metadata={
                    "matched_existing_canonical": local_candidate in canonical_values,
                    "hh_match_type": hh_result.match_type,
                    "hh_error": hh_result.error,
                },
            )

        logger.info(
            "Entity normalization profession fallback to agent: original_value={original_value}",
            original_value=original_value,
        )
        agent_result = await self.agent_client.normalize(
            normalization_class=NormalizationClass.PROFESSIONS,
            original_value=original_value,
            canonical_values=canonical_values,
        )
        normalized = (
            normalize_job_title(agent_result.normalized_value)
            if agent_result.normalized_value
            else None
        )
        return EntityNormalizationResult(
            original_value=original_value,
            normalization_class=NormalizationClass.PROFESSIONS,
            normalized_value=normalized,
            normalized_value_canonical=normalized,
            status=agent_result.status,
            provider="agent",
            confidence=agent_result.confidence,
            was_cache_hit=False,
            model_version=self.agent_client.model,
            pipeline_version=PIPELINE_VERSION,
            metadata={
                "matched_existing_canonical": agent_result.matched_existing_canonical,
                "rationale_short": agent_result.rationale_short,
                "canonical_count": len(canonical_values),
            },
        )


def build_lookup_value(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _clean_value(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", value).strip()
    return cleaned or None


def _seed_canonical_values(normalization_class: NormalizationClass) -> list[str]:
    if normalization_class == NormalizationClass.LANGUAGES:
        return LANGUAGE_CANONICAL
    if normalization_class == NormalizationClass.PROFICIENCY_LEVELS:
        return PROFICIENCY_CANONICAL_WITH_UNKNOWN
    if normalization_class == NormalizationClass.SENIORITY_LEVELS:
        return SENIORITY_CANONICAL_WITH_UNKNOWN
    if normalization_class == NormalizationClass.SKILLS:
        return SKILL_CANONICAL
    if normalization_class == NormalizationClass.PROFESSIONS:
        return PROFESSION_CANONICAL
    if normalization_class == NormalizationClass.REMOTE_POLICY:
        return REMOTE_POLICY_CANONICAL_LIST
    if normalization_class == NormalizationClass.EMPLOYMENT_TYPE:
        return EMPLOYMENT_TYPE_CANONICAL_LIST
    if normalization_class == NormalizationClass.EDUCATION:
        return EDUCATION_CANONICAL_LIST
    if normalization_class == NormalizationClass.CITIES:
        return list(dict.fromkeys(CITY_SYNONYMS.values()))
    if normalization_class == NormalizationClass.COUNTRIES:
        return list(dict.fromkeys(COUNTRY_SYNONYMS.values()))
    return []


def _deterministic_normalize(
    *,
    original_value: str,
    normalization_class: NormalizationClass,
    canonical_values: list[str],
) -> str | None:
    if normalization_class == NormalizationClass.LANGUAGES:
        normalized = normalize_language_name(original_value)
        if normalized and (
            build_lookup_value(normalized) in {build_lookup_value(item) for item in canonical_values}
            or build_lookup_value(original_value) in LANGUAGE_NAME_SYNONYMS
        ):
            return normalized
        return None
    if normalization_class == NormalizationClass.PROFICIENCY_LEVELS:
        normalized = normalize_language_level(original_value)
        if normalized and (
            normalized in canonical_values
            or build_lookup_value(original_value) in LANGUAGE_LEVEL_LOOKUPS
        ):
            return normalized
        return None
    if normalization_class == NormalizationClass.SENIORITY_LEVELS:
        return infer_seniority(original_value)
    if normalization_class == NormalizationClass.PROFESSIONS:
        normalized_input = build_lookup_value(original_value)
        if any(synonym in normalized_input for synonym in JOB_TITLE_CLUSTERS):
            return normalize_job_title(original_value)
        return None
    if normalization_class == NormalizationClass.REMOTE_POLICY:
        normalized_input = build_lookup_value(original_value)
        if normalized_input in REMOTE_POLICY_MAP:
            return normalize_remote_policy(original_value)
        return None
    if normalization_class == NormalizationClass.EMPLOYMENT_TYPE:
        normalized_input = build_lookup_value(original_value)
        if normalized_input in EMPLOYMENT_TYPE_MAP:
            return normalize_employment_type(original_value)
        return None
    if normalization_class == NormalizationClass.EDUCATION:
        normalized_input = build_lookup_value(original_value)
        if any(synonym in normalized_input for synonym in DEGREE_SYNONYMS):
            return normalize_degree(original_value)
        return None
    if normalization_class == NormalizationClass.CITIES:
        lookup = build_lookup_value(original_value).replace("г. ", "").replace("city ", "")
        return CITY_SYNONYMS.get(lookup)
    if normalization_class == NormalizationClass.COUNTRIES:
        return COUNTRY_SYNONYMS.get(build_lookup_value(original_value))
    return None


def _loads_metadata(value: str | None) -> dict | None:
    if not value:
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


LANGUAGE_LEVEL_LOOKUPS = set(value.strip().lower() for value in LANGUAGE_LEVELS)
