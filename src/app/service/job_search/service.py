from __future__ import annotations

import json
import uuid
from dataclasses import dataclass

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.enums.processing_stage import ProcessingStage
from app.models.candidate_search import CandidateLanguageFilter, CandidateSearchFilters
from app.models.job_search import JobSearchPreparationRequest
from app.service.job_search.graph import (
    JobSearchPreparationError,
    JobSearchPreparationGraph,
)
from app.service.job_search.llm_client import JobSearchPreparationLLMClient
from app.service.normalization.service import EntityNormalizationService
from app.service.skills.hh_skill_normalizer import HHSkillNormalizerService
from database.postgres.crud.cv import (
    JobDomainRepository,
    JobProcessingRunRepository,
    JobRequiredLanguageRepository,
    JobRequiredSkillRepository,
    JobSearchProfileRepository,
)

PIPELINE_VERSION = "job_search_preparation_mvp_v1"


@dataclass
class JobSearchPreparationService:
    """Service layer for preparing vacancy text into a persisted search-ready object."""

    session: AsyncSession
    llm_client: JobSearchPreparationLLMClient | None = None
    skill_normalizer: HHSkillNormalizerService | None = None
    normalization_service: EntityNormalizationService | None = None

    def __post_init__(self) -> None:
        self.profiles = JobSearchProfileRepository(self.session)
        self.languages = JobRequiredLanguageRepository(self.session)
        self.skills = JobRequiredSkillRepository(self.session)
        self.domains = JobDomainRepository(self.session)
        self.processing_runs = JobProcessingRunRepository(self.session)
        self.llm_client = self.llm_client or JobSearchPreparationLLMClient()
        self.skill_normalizer = self.skill_normalizer or HHSkillNormalizerService()

    async def run(self, payload: JobSearchPreparationRequest) -> CandidateSearchFilters:
        """Prepare and persist a vacancy search representation for one job."""

        job_id = payload.job_id or str(uuid.uuid4())
        source_document_id = payload.source_document_id
        logger.info(
            "Job search preparation service: requested run for job_id={job_id}, source_document_id={source_document_id}",
            job_id=job_id,
            source_document_id=source_document_id,
        )
        run = await self.processing_runs.mark_started(
            job_id=job_id,
            source_document_id=source_document_id,
            pipeline_stage=ProcessingStage.JOB_SEARCH_PREPARATION,
            pipeline_version=PIPELINE_VERSION,
            model_version=self.llm_client.model,
        )
        await self.session.commit()

        graph = JobSearchPreparationGraph(
            session=self.session,
            llm_client=self.llm_client,
            skill_normalizer=self.skill_normalizer,
            normalization_service=self.normalization_service,
        )

        try:
            state = await graph.graph.ainvoke(
                {
                    "job_id": job_id,
                    "source_document_id": source_document_id,
                    "raw_text": payload.raw_text,
                    "processing_metadata": {
                        "pipeline_version": PIPELINE_VERSION,
                        "model_version": self.llm_client.model,
                    },
                    "warnings": [],
                    "errors": [],
                }
            )
            await self.processing_runs.mark_completed(
                run,
                extraction_confidence=state["normalized_job"].extraction_confidence,
            )
            await self.session.commit()
            logger.info(
                "Job search preparation service: run completed for job_id={job_id}",
                job_id=job_id,
            )
            return await self.get_result(job_id)
        except Exception as exc:
            logger.exception(
                "Job search preparation service: run failed for job_id={job_id}, error={error}",
                job_id=job_id,
                error=str(exc),
            )
            await self.session.rollback()
            await self.processing_runs.mark_failed(
                job_id=job_id,
                source_document_id=source_document_id,
                pipeline_stage=ProcessingStage.JOB_SEARCH_PREPARATION,
                pipeline_version=PIPELINE_VERSION,
                model_version=self.llm_client.model,
                error_message=str(exc),
            )
            await self.session.commit()
            if isinstance(exc, JobSearchPreparationError):
                raise
            raise JobSearchPreparationError(str(exc)) from exc

    async def get_result(self, job_id: str) -> CandidateSearchFilters:
        """Return the persisted search-ready vacancy representation for one job."""

        profile = await self.profiles.get_by_job_id(job_id)
        if profile is None:
            raise JobSearchPreparationError("Prepared job search profile not found")

        languages = await self.languages.list_by_profile_id(
            profile.job_search_profile_id
        )
        skills = await self.skills.list_by_profile_id(profile.job_search_profile_id)
        domains = await self.domains.list_by_profile_id(profile.job_search_profile_id)
        run = await self.processing_runs.get_by_job_and_stage(
            job_id,
            ProcessingStage.JOB_SEARCH_PREPARATION,
        )

        required_skills = [item.normalized_skill for item in skills if item.is_required]
        optional_skills = [
            item.normalized_skill for item in skills if not item.is_required
        ]
        education_requirements = _parse_json_array(profile.education_requirements)
        certification_requirements = _parse_json_array(
            profile.certification_requirements
        )
        return CandidateSearchFilters(
            job_id=profile.job_id,
            source_document_id=profile.source_document_id,
            title_raw=profile.raw_title,
            query_text=profile.semantic_query_text_main,
            query_text_responsibilities=profile.semantic_query_text_responsibilities,
            query_text_skills=profile.semantic_query_text_skills,
            current_title_normalized=(
                [profile.normalized_title] if profile.normalized_title else None
            ),
            seniority_normalized=(
                [profile.seniority_normalized] if profile.seniority_normalized else None
            ),
            min_total_experience_months=profile.min_experience_months,
            location_normalized=(
                [profile.location_normalized] if profile.location_normalized else None
            ),
            remote_policies=(
                _parse_json_array(profile.remote_policies_json)
                or ([profile.remote_policy] if profile.remote_policy else None)
            ),
            employment_types=(
                _parse_json_array(profile.employment_types_json)
                or ([profile.employment_type] if profile.employment_type else None)
            ),
            languages=(
                [
                    CandidateLanguageFilter(
                        language_normalized=item.language_normalized,
                        min_proficiency_normalized=item.min_proficiency_normalized,
                    )
                    for item in languages
                ]
                or None
            ),
            require_all_languages=bool(languages),
            include_skills=required_skills or None,
            optional_skills=optional_skills or None,
            require_all_skills=bool(required_skills),
            domains=[item.domain_normalized for item in domains] or None,
            degree_normalized=education_requirements or None,
            certifications=certification_requirements or None,
            processing_status=run.status if run else None,
            pipeline_version=run.pipeline_version if run else None,
            model_version=run.model_version if run else None,
            extraction_confidence=run.extraction_confidence if run else None,
            error_message=run.error_message if run else None,
            started_at=run.started_at if run else None,
            finished_at=run.finished_at if run else None,
        )


def _parse_json_array(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [item for item in parsed if isinstance(item, str)]
