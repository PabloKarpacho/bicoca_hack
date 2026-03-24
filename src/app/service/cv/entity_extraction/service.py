from __future__ import annotations

import json
from dataclasses import dataclass

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.enums.processing_stage import ProcessingStage
from app.models.entity_extraction import (
    CandidateCertificationData,
    CandidateEducationData,
    CandidateEntitiesResponse,
    CandidateExperienceData,
    CandidateLanguageData,
    CandidateProfileData,
    CandidateSkillData,
    EntityExtractionRunResponse,
    ProcessingRunResponse,
)
from app.service.cv.entity_extraction.graph import (
    CandidateEntityExtractionGraph,
    EntityExtractionGraphError,
)
from app.service.cv.entity_extraction.llm_client import CVEntityExtractionLLMClient
from app.service.normalization.candidate_entities import compute_overall_confidence
from app.service.normalization.service import EntityNormalizationService
from app.service.skills.hh_skill_normalizer import HHSkillNormalizerService
from database.postgres.crud.cv import (
    CandidateCertificationRepository,
    CandidateDocumentRepository,
    CandidateEducationRepository,
    CandidateExperienceRepository,
    CandidateLanguageRepository,
    CandidateProfileRepository,
    CandidateSkillRepository,
    DocumentProcessingRunRepository,
)

PIPELINE_VERSION = "cv_entity_extraction_mvp_v1"


@dataclass
class CandidateEntityExtractionService:
    session: AsyncSession
    llm_client: CVEntityExtractionLLMClient | None = None
    skill_normalizer: HHSkillNormalizerService | None = None
    normalization_service: EntityNormalizationService | None = None

    def __post_init__(self) -> None:
        self.documents = CandidateDocumentRepository(self.session)
        self.profiles = CandidateProfileRepository(self.session)
        self.languages = CandidateLanguageRepository(self.session)
        self.experiences = CandidateExperienceRepository(self.session)
        self.skills = CandidateSkillRepository(self.session)
        self.education = CandidateEducationRepository(self.session)
        self.certifications = CandidateCertificationRepository(self.session)
        self.processing_runs = DocumentProcessingRunRepository(self.session)
        self.llm_client = self.llm_client or CVEntityExtractionLLMClient()

    async def run(self, document_id: str) -> EntityExtractionRunResponse:
        logger.info(
            "Entity extraction service: requested run for document_id={document_id}",
            document_id=document_id,
        )
        document = await self.documents.get_plain_by_id(document_id)
        if document is None:
            logger.warning(
                "Entity extraction service: document not found for document_id={document_id}",
                document_id=document_id,
            )
            raise EntityExtractionGraphError("Document not found")
        candidate_id = document.candidate_id

        logger.info(
            "Entity extraction service: marking extraction started for document_id={document_id}, candidate_id={candidate_id}, pipeline_version={pipeline_version}, model_version={model_version}",
            document_id=document_id,
            candidate_id=candidate_id,
            pipeline_version=PIPELINE_VERSION,
            model_version=self.llm_client.model,
        )
        run = await self.processing_runs.mark_started(
            document_id=document_id,
            candidate_id=candidate_id,
            processing_stage=ProcessingStage.ENTITY_EXTRACTION,
            pipeline_version=PIPELINE_VERSION,
            model_version=self.llm_client.model,
        )
        await self.session.commit()
        logger.info(
            "Entity extraction service: extraction started for document_id={document_id}",
            document_id=document_id,
        )

        graph = CandidateEntityExtractionGraph(
            session=self.session,
            llm_client=self.llm_client,
            skill_normalizer=self.skill_normalizer,
            normalization_service=self.normalization_service,
        )

        try:
            logger.info(
                "Entity extraction service: invoking graph for document_id={document_id}",
                document_id=document_id,
            )
            state = await graph.graph.ainvoke(
                {
                    "document_id": document_id,
                    "processing_metadata": {
                        "pipeline_version": PIPELINE_VERSION,
                        "model_version": self.llm_client.model,
                    },
                    "warnings": [],
                    "errors": [],
                }
            )
            normalized = state["normalized_entities"]
            confidence = compute_overall_confidence(normalized)
            logger.info(
                "Entity extraction service: graph completed for document_id={document_id}, extraction_confidence={extraction_confidence}",
                document_id=document_id,
                extraction_confidence=confidence,
            )
            await self.processing_runs.mark_completed(
                run,
                extraction_confidence=confidence,
            )
            await self.session.commit()
            logger.info(
                "Entity extraction service: extraction marked completed for document_id={document_id}",
                document_id=document_id,
            )
            return EntityExtractionRunResponse(
                document_id=document_id,
                candidate_id=candidate_id,
                status=run.status,
                pipeline_version=run.pipeline_version,
                model_version=run.model_version,
                extraction_confidence=run.extraction_confidence,
            )
        except Exception as exc:
            logger.exception(
                "Entity extraction service: extraction failed for document_id={document_id}, candidate_id={candidate_id}, error={error}",
                document_id=document_id,
                candidate_id=candidate_id,
                error=str(exc),
            )
            await self.session.rollback()
            run = await self.processing_runs.mark_failed(
                document_id=document_id,
                candidate_id=candidate_id,
                processing_stage=ProcessingStage.ENTITY_EXTRACTION,
                pipeline_version=PIPELINE_VERSION,
                model_version=self.llm_client.model,
                error_message=str(exc),
            )
            await self.session.commit()
            if isinstance(exc, EntityExtractionGraphError):
                raise
            raise EntityExtractionGraphError(str(exc)) from exc

    async def get_result(self, document_id: str) -> CandidateEntitiesResponse:
        logger.info(
            "Entity extraction service: loading persisted result for document_id={document_id}",
            document_id=document_id,
        )
        document = await self.documents.get_by_id(document_id)
        if document is None:
            logger.warning(
                "Entity extraction service: result requested for missing document_id={document_id}",
                document_id=document_id,
            )
            raise EntityExtractionGraphError("Document not found")

        profile = await self.profiles.get_by_document_id(document_id)
        languages = await self.languages.list_by_document_id(document_id)
        experiences = await self.experiences.list_by_document_id(document_id)
        skills = await self.skills.list_by_document_id(document_id)
        education = await self.education.list_by_document_id(document_id)
        certifications = await self.certifications.list_by_document_id(document_id)
        run = await self.processing_runs.get_by_document_and_stage(
            document_id,
            ProcessingStage.ENTITY_EXTRACTION,
        )
        logger.info(
            "Entity extraction service: loaded persisted result for document_id={document_id}, profile_present={profile_present}, languages={languages}, experiences={experiences}, skills={skills}, education={education}, certifications={certifications}, has_processing_run={has_processing_run}",
            document_id=document_id,
            profile_present=profile is not None,
            languages=len(languages),
            experiences=len(experiences),
            skills=len(skills),
            education=len(education),
            certifications=len(certifications),
            has_processing_run=run is not None,
        )

        return CandidateEntitiesResponse(
            document_id=document_id,
            candidate_id=document.candidate_id,
            processing_run=ProcessingRunResponse.model_validate(run) if run else None,
            profile=(
                CandidateProfileData(
                    full_name=profile.full_name,
                    email=profile.email,
                    phone=profile.phone,
                    location_raw=profile.location_raw,
                    linkedin_url=profile.linkedin_url,
                    github_url=profile.github_url,
                    portfolio_url=profile.portfolio_url,
                    headline=profile.headline,
                    summary=profile.summary,
                    current_title_raw=profile.current_title_raw,
                    current_title_normalized=profile.current_title_normalized,
                    seniority_normalized=profile.seniority_normalized,
                    remote_policies=_parse_json_array(profile.remote_policies_json),
                    employment_types=_parse_json_array(profile.employment_types_json),
                    total_experience_months=profile.total_experience_months,
                    extraction_confidence=profile.extraction_confidence,
                )
                if profile
                else None
            ),
            languages=[
                CandidateLanguageData(
                    language_raw=item.language_raw,
                    language_normalized=item.language_normalized,
                    proficiency_raw=item.proficiency_raw,
                    proficiency_normalized=item.proficiency_normalized,
                    confidence=item.confidence,
                )
                for item in languages
            ],
            experiences=[
                CandidateExperienceData(
                    position_order=item.position_order,
                    company_name_raw=item.company_name_raw,
                    job_title_raw=item.job_title_raw,
                    job_title_normalized=item.job_title_normalized,
                    start_date=item.start_date,
                    end_date=item.end_date,
                    is_current=item.is_current,
                    duration_months=item.duration_months,
                    location_raw=item.location_raw,
                    responsibilities_text=item.responsibilities_text,
                    technologies_text=item.technologies_text,
                    domain_hint=item.domain_hint,
                    confidence=item.confidence,
                )
                for item in experiences
            ],
            skills=[
                CandidateSkillData(
                    raw_skill=item.raw_skill,
                    normalized_skill=item.normalized_skill,
                    skill_category=item.skill_category,
                    source_type=item.source_type,
                    confidence=item.confidence,
                    normalization_source=item.normalization_source,
                    normalization_external_id=item.normalization_external_id,
                    normalization_status=item.normalization_status,
                    normalization_confidence=item.normalization_confidence,
                    normalization_metadata=(
                        json.loads(item.normalization_metadata_json)
                        if item.normalization_metadata_json
                        else None
                    ),
                )
                for item in skills
            ],
            education=[
                CandidateEducationData(
                    position_order=item.position_order,
                    institution_raw=item.institution_raw,
                    degree_raw=item.degree_raw,
                    degree_normalized=item.degree_normalized,
                    field_of_study=item.field_of_study,
                    start_date=item.start_date,
                    end_date=item.end_date,
                    confidence=item.confidence,
                )
                for item in education
            ],
            certifications=[
                CandidateCertificationData(
                    certification_name_raw=item.certification_name_raw,
                    certification_name_normalized=item.certification_name_normalized,
                    issuer=item.issuer,
                    issue_date=item.issue_date,
                    expiry_date=item.expiry_date,
                    confidence=item.confidence,
                )
                for item in certifications
            ],
        )


def _parse_json_array(value: str | None) -> list[str] | None:
    if not value:
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, list):
        return None
    items = [item for item in parsed if isinstance(item, str)]
    return items or None
