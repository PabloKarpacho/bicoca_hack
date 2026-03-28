from __future__ import annotations

import json
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entity_extraction import (
    CVEntityExtractionLLMOutput,
    CandidateEntitiesData,
)
from app.service.cv.entity_extraction.llm_client import CVEntityExtractionLLMClient
from app.service.normalization.candidate_entities import normalize_entities
from app.service.normalization.service import EntityNormalizationService
from app.service.skills.hh_skill_normalizer import HHSkillNormalizerService
from database.postgres.crud.cv import (
    CandidateCertificationRepository,
    CandidateDocumentRepository,
    CandidateDocumentTextRepository,
    CandidateEducationRepository,
    CandidateExperienceRepository,
    CandidateLanguageRepository,
    CandidateProfileRepository,
    CandidateSkillRepository,
)


class EntityExtractionGraphError(RuntimeError):
    pass


class EntityExtractionGraphState(TypedDict, total=False):
    document_id: str
    candidate_id: str | None
    raw_text: str
    extracted_entities: CVEntityExtractionLLMOutput
    normalized_entities: CandidateEntitiesData
    processing_metadata: dict[str, str | float | None]
    warnings: list[str]
    errors: list[str]


class CandidateEntityExtractionGraph:
    def __init__(
        self,
        *,
        session: AsyncSession,
        llm_client: CVEntityExtractionLLMClient | None = None,
        skill_normalizer: HHSkillNormalizerService | None = None,
        normalization_service: EntityNormalizationService | None = None,
    ) -> None:
        self.session = session
        self.documents = CandidateDocumentRepository(session)
        self.texts = CandidateDocumentTextRepository(session)
        self.profiles = CandidateProfileRepository(session)
        self.languages = CandidateLanguageRepository(session)
        self.experiences = CandidateExperienceRepository(session)
        self.skills = CandidateSkillRepository(session)
        self.education = CandidateEducationRepository(session)
        self.certifications = CandidateCertificationRepository(session)
        self.llm_client = llm_client or CVEntityExtractionLLMClient()
        self.skill_normalizer = skill_normalizer or HHSkillNormalizerService()
        self.normalization_service = (
            normalization_service
            or EntityNormalizationService(
                session=session,
                skill_normalizer=self.skill_normalizer,
            )
        )
        self.graph = self._build_graph()

    def _build_graph(self):
        builder = StateGraph(EntityExtractionGraphState)
        builder.add_node("load_document_text", self.load_document_text)
        builder.add_node("extract_entities", self.extract_entities)
        builder.add_node("normalize_entities", self.normalize_entities)
        builder.add_node("persist_entities", self.persist_entities)
        builder.add_edge(START, "load_document_text")
        builder.add_edge("load_document_text", "extract_entities")
        builder.add_edge("extract_entities", "normalize_entities")
        builder.add_edge("normalize_entities", "persist_entities")
        builder.add_edge("persist_entities", END)
        return builder.compile()

    @staticmethod
    def _entity_counts(normalized: CandidateEntitiesData) -> dict[str, int]:
        return {
            "languages": len(normalized.languages),
            "experiences": len(normalized.experiences),
            "skills": len(normalized.skills),
            "education": len(normalized.education),
            "certifications": len(normalized.certifications),
        }

    async def load_document_text(
        self,
        state: EntityExtractionGraphState,
    ) -> EntityExtractionGraphState:
        document_id = state["document_id"]
        logger.info(
            "Entity extraction graph: entering load_document_text for document_id={document_id}",
            document_id=document_id,
        )
        document = await self.documents.get_plain_by_id(document_id)
        if document is None:
            logger.warning(
                "Entity extraction graph: document not found in load_document_text for document_id={document_id}",
                document_id=document_id,
            )
            raise EntityExtractionGraphError("Document not found")
        document_text = await self.texts.get_by_document_id(document_id)
        if document_text is None or not document_text.raw_text.strip():
            logger.warning(
                "Entity extraction graph: raw_text missing in load_document_text for document_id={document_id}",
                document_id=document_id,
            )
            raise EntityExtractionGraphError(
                "Raw text is missing for entity extraction"
            )
        logger.info(
            "Entity extraction graph: loaded raw_text for document_id={document_id}, candidate_id={candidate_id}, char_count={char_count}",
            document_id=document_id,
            candidate_id=document.candidate_id,
            char_count=len(document_text.raw_text),
        )
        return {
            "candidate_id": document.candidate_id,
            "raw_text": document_text.raw_text,
        }

    async def extract_entities(
        self,
        state: EntityExtractionGraphState,
    ) -> EntityExtractionGraphState:
        logger.info(
            "Entity extraction graph: entering extract_entities for document_id={document_id}, model={model}, raw_text_chars={char_count}",
            document_id=state["document_id"],
            model=self.llm_client.model,
            char_count=len(state["raw_text"]),
        )
        extracted = await self.llm_client.extract_entities(state["raw_text"])
        logger.info(
            "Entity extraction graph: extracted entities for document_id={document_id}, languages={languages}, experiences={experiences}, skills={skills}, education={education}, certifications={certifications}",
            document_id=state["document_id"],
            languages=len(extracted.languages),
            experiences=len(extracted.experiences),
            skills=len(extracted.skills),
            education=len(extracted.education),
            certifications=len(extracted.certifications),
        )
        return {
            "extracted_entities": extracted,
        }

    async def normalize_entities(
        self,
        state: EntityExtractionGraphState,
    ) -> EntityExtractionGraphState:
        logger.info(
            "Entity extraction graph: entering normalize_entities for document_id={document_id}",
            document_id=state["document_id"],
        )
        document = await self.documents.get_by_id(state["document_id"])
        normalized = await normalize_entities(
            raw_text=state["raw_text"],
            extracted=state["extracted_entities"],
            candidate_full_name=document.candidate.full_name if document else None,
            candidate_email=document.candidate.email if document else None,
            normalization_service=self.normalization_service,
            skill_normalizer=self.skill_normalizer,
        )
        counts = self._entity_counts(normalized)
        logger.info(
            "Entity extraction graph: normalized entities for document_id={document_id}, profile_present={profile_present}, languages={languages}, experiences={experiences}, skills={skills}, education={education}, certifications={certifications}, total_experience_months={total_experience_months}",
            document_id=state["document_id"],
            profile_present=normalized.profile is not None,
            languages=counts["languages"],
            experiences=counts["experiences"],
            skills=counts["skills"],
            education=counts["education"],
            certifications=counts["certifications"],
            total_experience_months=normalized.profile.total_experience_months,
        )
        return {
            "normalized_entities": normalized,
        }

    async def persist_entities(
        self,
        state: EntityExtractionGraphState,
    ) -> EntityExtractionGraphState:
        document_id = state["document_id"]
        candidate_id = state["candidate_id"]
        normalized = state["normalized_entities"]
        counts = self._entity_counts(normalized)

        logger.info(
            "Entity extraction graph: entering persist_entities for document_id={document_id}, candidate_id={candidate_id}",
            document_id=document_id,
            candidate_id=candidate_id,
        )
        logger.debug(
            "Entity extraction graph: replacing persisted entities for document_id={document_id}, languages={languages}, experiences={experiences}, skills={skills}, education={education}, certifications={certifications}",
            document_id=document_id,
            languages=counts["languages"],
            experiences=counts["experiences"],
            skills=counts["skills"],
            education=counts["education"],
            certifications=counts["certifications"],
        )

        await self.profiles.delete_by_document_id(document_id)
        await self.languages.delete_by_document_id(document_id)
        await self.experiences.delete_by_document_id(document_id)
        await self.skills.delete_by_document_id(document_id)
        await self.education.delete_by_document_id(document_id)
        await self.certifications.delete_by_document_id(document_id)

        await self.profiles.create(
            candidate_id=candidate_id,
            document_id=document_id,
            full_name=normalized.profile.full_name,
            email=normalized.profile.email,
            phone=normalized.profile.phone,
            location_raw=normalized.profile.location_raw,
            linkedin_url=normalized.profile.linkedin_url,
            github_url=normalized.profile.github_url,
            portfolio_url=normalized.profile.portfolio_url,
            headline=normalized.profile.headline,
            summary=normalized.profile.summary,
            current_title_raw=normalized.profile.current_title_raw,
            current_title_normalized=normalized.profile.current_title_normalized,
            seniority_normalized=normalized.profile.seniority_normalized,
            remote_policies_json=(
                json.dumps(normalized.profile.remote_policies, ensure_ascii=False)
                if normalized.profile.remote_policies is not None
                else None
            ),
            employment_types_json=(
                json.dumps(normalized.profile.employment_types, ensure_ascii=False)
                if normalized.profile.employment_types is not None
                else None
            ),
            total_experience_months=normalized.profile.total_experience_months,
            extraction_confidence=normalized.profile.extraction_confidence,
        )

        for item in normalized.languages:
            await self.languages.create(
                candidate_id=candidate_id,
                document_id=document_id,
                language_raw=item.language_raw,
                language_normalized=item.language_normalized,
                proficiency_raw=item.proficiency_raw,
                proficiency_normalized=item.proficiency_normalized,
                confidence=item.confidence,
            )

        for item in normalized.experiences:
            await self.experiences.create(
                candidate_id=candidate_id,
                document_id=document_id,
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

        for item in normalized.skills:
            await self.skills.create(
                candidate_id=candidate_id,
                document_id=document_id,
                raw_skill=item.raw_skill,
                normalized_skill=item.normalized_skill,
                skill_category=item.skill_category,
                source_type=item.source_type,
                confidence=item.confidence,
                normalization_source=item.normalization_source,
                normalization_external_id=item.normalization_external_id,
                normalization_status=item.normalization_status,
                normalization_confidence=item.normalization_confidence,
                normalization_metadata_json=(
                    json.dumps(item.normalization_metadata, ensure_ascii=False)
                    if item.normalization_metadata is not None
                    else None
                ),
            )

        for item in normalized.education:
            await self.education.create(
                candidate_id=candidate_id,
                document_id=document_id,
                position_order=item.position_order,
                institution_raw=item.institution_raw,
                degree_raw=item.degree_raw,
                degree_normalized=item.degree_normalized,
                field_of_study=item.field_of_study,
                start_date=item.start_date,
                end_date=item.end_date,
                confidence=item.confidence,
            )

        for item in normalized.certifications:
            await self.certifications.create(
                candidate_id=candidate_id,
                document_id=document_id,
                certification_name_raw=item.certification_name_raw,
                certification_name_normalized=item.certification_name_normalized,
                issuer=item.issuer,
                issue_date=item.issue_date,
                expiry_date=item.expiry_date,
                confidence=item.confidence,
            )

        await self.session.flush()
        logger.info(
            "Entity extraction graph: persisted entities for document_id={document_id}, languages={languages}, experiences={experiences}, skills={skills}, education={education}, certifications={certifications}",
            document_id=document_id,
            languages=counts["languages"],
            experiences=counts["experiences"],
            skills=counts["skills"],
            education=counts["education"],
            certifications=counts["certifications"],
        )
        return state
