from __future__ import annotations

import json
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entity_extraction import JobSearchExtractionLLMOutput
from app.models.job_search import PreparedJobSearchData
from app.service.job_search.llm_client import JobSearchPreparationLLMClient
from app.service.normalization.job_preparation import normalize_job_search_requirements
from app.service.normalization.service import EntityNormalizationService
from app.service.skills.hh_skill_normalizer import HHSkillNormalizerService
from database.postgres.crud.cv import (
    JobDomainRepository,
    JobRequiredLanguageRepository,
    JobRequiredSkillRepository,
    JobSearchProfileRepository,
)


class JobSearchPreparationError(RuntimeError):
    pass


class JobSearchGraphState(TypedDict, total=False):
    job_id: str
    source_document_id: str | None
    raw_text: str
    extracted_requirements: JobSearchExtractionLLMOutput
    normalized_job: PreparedJobSearchData
    processing_metadata: dict[str, str | float | None]
    warnings: list[str]
    errors: list[str]


class JobSearchPreparationGraph:
    """LangGraph flow for turning a vacancy description into a search-ready object."""

    def __init__(
        self,
        *,
        session: AsyncSession,
        llm_client: JobSearchPreparationLLMClient | None = None,
        skill_normalizer: HHSkillNormalizerService | None = None,
        normalization_service: EntityNormalizationService | None = None,
    ) -> None:
        self.session = session
        self.profiles = JobSearchProfileRepository(session)
        self.languages = JobRequiredLanguageRepository(session)
        self.skills = JobRequiredSkillRepository(session)
        self.domains = JobDomainRepository(session)
        self.llm_client = llm_client or JobSearchPreparationLLMClient()
        self.skill_normalizer = skill_normalizer or HHSkillNormalizerService()
        self.normalization_service = normalization_service or EntityNormalizationService(
            session=session,
            skill_normalizer=self.skill_normalizer,
        )
        self.graph = self._build_graph()

    def _build_graph(self):
        builder = StateGraph(JobSearchGraphState)
        builder.add_node("load_job_text", self.load_job_text)
        builder.add_node(
            "extract_job_search_requirements",
            self.extract_job_search_requirements,
        )
        builder.add_node(
            "normalize_job_search_requirements",
            self.normalize_job_search_requirements,
        )
        builder.add_node(
            "persist_job_search_representation",
            self.persist_job_search_representation,
        )
        builder.add_edge(START, "load_job_text")
        builder.add_edge("load_job_text", "extract_job_search_requirements")
        builder.add_edge(
            "extract_job_search_requirements",
            "normalize_job_search_requirements",
        )
        builder.add_edge(
            "normalize_job_search_requirements",
            "persist_job_search_representation",
        )
        builder.add_edge("persist_job_search_representation", END)
        return builder.compile()

    async def load_job_text(self, state: JobSearchGraphState) -> JobSearchGraphState:
        job_id = state["job_id"]
        logger.info(
            "Job search preparation graph: entering load_job_text for job_id={job_id}",
            job_id=job_id,
        )
        raw_text = state.get("raw_text", "")
        normalized = raw_text.strip()
        if not normalized:
            logger.warning(
                "Job search preparation graph: raw_text missing for job_id={job_id}",
                job_id=job_id,
            )
            raise JobSearchPreparationError("Raw text is missing for job preparation")
        logger.info(
            "Job search preparation graph: validated raw_text for job_id={job_id}, char_count={char_count}",
            job_id=job_id,
            char_count=len(normalized),
        )
        return {"raw_text": normalized}

    async def extract_job_search_requirements(
        self,
        state: JobSearchGraphState,
    ) -> JobSearchGraphState:
        logger.info(
            "Job search preparation graph: entering extract_job_search_requirements for job_id={job_id}, model={model}, raw_text_chars={char_count}",
            job_id=state["job_id"],
            model=self.llm_client.model,
            char_count=len(state["raw_text"]),
        )
        extracted = await self.llm_client.extract_requirements(state["raw_text"])
        logger.info(
            "Job search preparation graph: extracted requirements for job_id={job_id}, languages={languages}, skills={skills}, education={education}, certifications={certifications}, domains={domains}",
            job_id=state["job_id"],
            languages=len(extracted.languages),
            skills=len(extracted.skills),
            education=len(extracted.education),
            certifications=len(extracted.certifications),
            domains=len(extracted.domains),
        )
        return {"extracted_requirements": extracted}

    async def normalize_job_search_requirements(
        self,
        state: JobSearchGraphState,
    ) -> JobSearchGraphState:
        logger.info(
            "Job search preparation graph: entering normalize_job_search_requirements for job_id={job_id}",
            job_id=state["job_id"],
        )
        normalized = await normalize_job_search_requirements(
            raw_text=state["raw_text"],
            extracted=state["extracted_requirements"],
            normalization_service=self.normalization_service,
            skill_normalizer=self.skill_normalizer,
        )
        logger.info(
            "Job search preparation graph: normalized vacancy for job_id={job_id}, required_languages={required_languages}, required_skills={required_skills}, optional_skills={optional_skills}, domains={domains}",
            job_id=state["job_id"],
            required_languages=len(normalized.rule_filters.required_languages),
            required_skills=len(normalized.rule_filters.required_skills),
            optional_skills=len(normalized.rule_filters.optional_skills),
            domains=len(normalized.rule_filters.domains),
        )
        return {"normalized_job": normalized}

    async def persist_job_search_representation(
        self,
        state: JobSearchGraphState,
    ) -> JobSearchGraphState:
        job_id = state["job_id"]
        source_document_id = state.get("source_document_id")
        normalized = state["normalized_job"]
        logger.info(
            "Job search preparation graph: entering persist_job_search_representation for job_id={job_id}",
            job_id=job_id,
        )

        existing = await self.profiles.get_by_job_id(job_id)
        if existing is not None:
            await self.languages.delete_by_profile_id(existing.job_search_profile_id)
            await self.skills.delete_by_profile_id(existing.job_search_profile_id)
            await self.domains.delete_by_profile_id(existing.job_search_profile_id)
            await self.profiles.delete_by_job_id(job_id)

        profile = await self.profiles.create(
            job_id=job_id,
            source_document_id=source_document_id,
            raw_title=normalized.rule_filters.title_raw,
            normalized_title=normalized.rule_filters.title_normalized,
            seniority_normalized=normalized.rule_filters.seniority_normalized,
            location_raw=normalized.rule_filters.location_raw,
            location_normalized=normalized.rule_filters.location_normalized,
            remote_policies_json=(
                json.dumps(normalized.rule_filters.remote_policies, ensure_ascii=False)
                if normalized.rule_filters.remote_policies is not None
                else None
            ),
            employment_types_json=(
                json.dumps(normalized.rule_filters.employment_types, ensure_ascii=False)
                if normalized.rule_filters.employment_types is not None
                else None
            ),
            employment_type=(
                normalized.rule_filters.employment_types[0]
                if normalized.rule_filters.employment_types
                else None
            ),
            min_experience_months=normalized.rule_filters.min_experience_months,
            education_requirements=json.dumps(
                normalized.rule_filters.education_requirements,
                ensure_ascii=False,
            ),
            certification_requirements=json.dumps(
                normalized.rule_filters.certification_requirements,
                ensure_ascii=False,
            ),
            semantic_query_text_main=normalized.vector_queries.main_query_text,
            semantic_query_text_responsibilities=normalized.vector_queries.responsibilities_query_text,
            semantic_query_text_skills=normalized.vector_queries.skills_query_text,
            extraction_confidence=normalized.extraction_confidence,
            pipeline_version=str(state["processing_metadata"].get("pipeline_version")),
            model_version=state["processing_metadata"].get("model_version"),
        )

        for item in normalized.rule_filters.required_languages:
            await self.languages.create(
                job_search_profile_id=profile.job_search_profile_id,
                language_normalized=item.language_normalized,
                min_proficiency_normalized=item.min_proficiency_normalized,
                is_required=item.is_required,
            )

        for skill in normalized.rule_filters.required_skills:
            await self.skills.create(
                job_search_profile_id=profile.job_search_profile_id,
                normalized_skill=skill,
                is_required=True,
                source_type="must_have",
            )

        for skill in normalized.rule_filters.optional_skills:
            await self.skills.create(
                job_search_profile_id=profile.job_search_profile_id,
                normalized_skill=skill,
                is_required=False,
                source_type="nice_to_have",
            )

        for domain in normalized.rule_filters.domains:
            await self.domains.create(
                job_search_profile_id=profile.job_search_profile_id,
                domain_normalized=domain,
            )

        logger.info(
            "Job search preparation graph: persisted vacancy for job_id={job_id}, profile_id={profile_id}, required_languages={required_languages}, required_skills={required_skills}, optional_skills={optional_skills}, domains={domains}",
            job_id=job_id,
            profile_id=profile.job_search_profile_id,
            required_languages=len(normalized.rule_filters.required_languages),
            required_skills=len(normalized.rule_filters.required_skills),
            optional_skills=len(normalized.rule_filters.optional_skills),
            domains=len(normalized.rule_filters.domains),
        )
        return {}
