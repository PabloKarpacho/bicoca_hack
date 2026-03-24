from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config.enums.document_status import DocumentProcessingStatus
from app.config.enums.normalization_class import NormalizationClass
from app.config.enums.normalization_status import NormalizationStatus
from app.config.enums.processing_run_status import ProcessingRunStatus
from app.config.enums.processing_stage import ProcessingStage
from database.postgres.schema import (
    Candidate,
    CandidateCertification,
    CandidateDocument,
    CandidateDocumentChunk,
    CandidateDocumentText,
    CandidateEducation,
    CandidateExperience,
    CandidateLanguage,
    CandidateProfile,
    CandidateSkill,
    DocumentProcessingRun,
    EntityNormalization,
    JobDomain,
    JobProcessingRun,
    JobRequiredLanguage,
    JobRequiredSkill,
    JobSearchProfile,
)


@dataclass(slots=True)
class CandidateRepository:
    session: AsyncSession

    async def get_by_id(self, candidate_id: str) -> Candidate | None:
        return await self.session.get(Candidate, candidate_id)

    async def get_by_external_id(self, external_id: str) -> Candidate | None:
        result = await self.session.execute(
            select(Candidate).where(Candidate.external_id == external_id)
        )
        return result.scalars().first()

    async def get_by_email(self, email: str) -> Candidate | None:
        result = await self.session.execute(
            select(Candidate).where(Candidate.email == email)
        )
        return result.scalars().first()

    async def create(
        self,
        *,
        external_id: str | None,
        full_name: str | None,
        email: str | None,
    ) -> Candidate:
        candidate = Candidate(
            external_id=external_id,
            full_name=full_name,
            email=email,
        )
        self.session.add(candidate)
        await self.session.flush()
        await self.session.refresh(candidate)
        return candidate

    async def update(
        self,
        candidate: Candidate,
        *,
        full_name: str | None,
        email: str | None,
    ) -> Candidate:
        if full_name is not None:
            candidate.full_name = full_name
        if email is not None:
            candidate.email = email
        await self.session.flush()
        await self.session.refresh(candidate)
        return candidate


@dataclass(slots=True)
class CandidateDocumentRepository:
    session: AsyncSession

    async def get_plain_by_id(self, document_id: str) -> CandidateDocument | None:
        return await self.session.get(CandidateDocument, document_id)

    async def get_by_id(self, document_id: str) -> CandidateDocument | None:
        result = await self.session.execute(
            select(CandidateDocument)
            .options(
                selectinload(CandidateDocument.candidate),
                selectinload(CandidateDocument.text),
            )
            .where(CandidateDocument.document_id == document_id)
        )
        return result.scalars().first()

    async def get_by_candidate_and_checksum(
        self, candidate_id: str, checksum_sha256: str
    ) -> CandidateDocument | None:
        result = await self.session.execute(
            select(CandidateDocument).where(
                CandidateDocument.candidate_id == candidate_id,
                CandidateDocument.checksum_sha256 == checksum_sha256,
            )
        )
        return result.scalars().first()

    async def list_by_ids(self, document_ids: list[str]) -> list[CandidateDocument]:
        if not document_ids:
            return []
        result = await self.session.execute(
            select(CandidateDocument).where(
                CandidateDocument.document_id.in_(document_ids)
            )
        )
        return list(result.scalars().all())

    async def create(
        self,
        *,
        candidate_id: str,
        original_filename: str,
        file_extension: str,
        content_type: str | None,
        size_bytes: int,
        checksum_sha256: str,
        processing_status: DocumentProcessingStatus,
    ) -> CandidateDocument:
        document = CandidateDocument(
            candidate_id=candidate_id,
            original_filename=original_filename,
            file_extension=file_extension,
            content_type=content_type,
            size_bytes=size_bytes,
            checksum_sha256=checksum_sha256,
            processing_status=processing_status.value,
        )
        self.session.add(document)
        await self.session.flush()
        await self.session.refresh(document)
        return document

    async def update_storage(
        self,
        document: CandidateDocument,
        *,
        bucket: str,
        key: str,
        processing_status: DocumentProcessingStatus,
    ) -> CandidateDocument:
        document.storage_bucket = bucket
        document.storage_key = key
        document.processing_status = processing_status.value
        document.error_message = None
        await self.session.flush()
        await self.session.refresh(document)
        return document

    async def update_processing_status(
        self,
        document: CandidateDocument,
        *,
        status: DocumentProcessingStatus,
        extractor_name: str | None = None,
        extracted_char_count: int | None = None,
        error_message: str | None = None,
    ) -> CandidateDocument:
        document.processing_status = status.value
        document.extractor_name = extractor_name
        document.extracted_char_count = extracted_char_count
        document.error_message = error_message
        await self.session.flush()
        await self.session.refresh(document)
        return document

    async def update_indexing_status(
        self,
        document: CandidateDocument,
        *,
        indexing_status: str,
        error_message: str | None = None,
    ) -> CandidateDocument:
        document.indexing_status = indexing_status
        document.error_message = error_message
        await self.session.flush()
        await self.session.refresh(document)
        return document


@dataclass(slots=True)
class CandidateDocumentTextRepository:
    session: AsyncSession

    async def get_by_document_id(self, document_id: str) -> CandidateDocumentText | None:
        result = await self.session.execute(
            select(CandidateDocumentText).where(
                CandidateDocumentText.document_id == document_id
            )
        )
        return result.scalars().first()

    async def upsert(self, *, document_id: str, raw_text: str) -> CandidateDocumentText:
        result = await self.session.execute(
            select(CandidateDocumentText).where(
                CandidateDocumentText.document_id == document_id
            )
        )
        document_text = result.scalars().first()
        if document_text is None:
            document_text = CandidateDocumentText(
                document_id=document_id,
                raw_text=raw_text,
            )
            self.session.add(document_text)
        else:
            document_text.raw_text = raw_text
        await self.session.flush()
        await self.session.refresh(document_text)
        return document_text

    async def delete_by_document_id(self, document_id: str) -> None:
        await self.session.execute(
            delete(CandidateDocumentText).where(
                CandidateDocumentText.document_id == document_id
            )
        )


@dataclass(slots=True)
class CandidateDocumentChunkRepository:
    session: AsyncSession

    async def list_by_document_id(self, document_id: str) -> list[CandidateDocumentChunk]:
        result = await self.session.execute(
            select(CandidateDocumentChunk)
            .where(CandidateDocumentChunk.document_id == document_id)
            .order_by(
                CandidateDocumentChunk.chunk_type.asc(),
                CandidateDocumentChunk.created_at.asc(),
            )
        )
        return list(result.scalars().all())

    async def delete_by_document_id(self, document_id: str) -> None:
        await self.session.execute(
            delete(CandidateDocumentChunk).where(
                CandidateDocumentChunk.document_id == document_id
            )
        )

    async def delete_by_chunk_ids(self, chunk_ids: list[str]) -> None:
        if not chunk_ids:
            return
        await self.session.execute(
            delete(CandidateDocumentChunk).where(
                CandidateDocumentChunk.chunk_id.in_(chunk_ids)
            )
        )

    async def create(self, **values) -> CandidateDocumentChunk:
        item = CandidateDocumentChunk(**values)
        self.session.add(item)
        await self.session.flush()
        await self.session.refresh(item)
        return item

    async def update_indexing(
        self,
        chunk: CandidateDocumentChunk,
        *,
        embedding_status: str,
        embedding_model_version: str | None,
        qdrant_point_id: str | None,
    ) -> CandidateDocumentChunk:
        chunk.embedding_status = embedding_status
        chunk.embedding_model_version = embedding_model_version
        chunk.qdrant_point_id = qdrant_point_id
        await self.session.flush()
        await self.session.refresh(chunk)
        return chunk

    async def mark_reused(
        self,
        chunk: CandidateDocumentChunk,
        *,
        embedding_model_version: str | None,
    ) -> CandidateDocumentChunk:
        chunk.embedding_status = "indexed"
        chunk.embedding_model_version = embedding_model_version
        if not chunk.qdrant_point_id:
            chunk.qdrant_point_id = chunk.chunk_id
        await self.session.flush()
        await self.session.refresh(chunk)
        return chunk

@dataclass(slots=True)
class CandidateProfileRepository:
    session: AsyncSession

    async def get_by_document_id(self, document_id: str) -> CandidateProfile | None:
        result = await self.session.execute(
            select(CandidateProfile).where(CandidateProfile.document_id == document_id)
        )
        return result.scalars().first()

    async def delete_by_document_id(self, document_id: str) -> None:
        await self.session.execute(
            delete(CandidateProfile).where(CandidateProfile.document_id == document_id)
        )

    async def create(self, **values) -> CandidateProfile:
        profile = CandidateProfile(**values)
        self.session.add(profile)
        await self.session.flush()
        await self.session.refresh(profile)
        return profile


@dataclass(slots=True)
class CandidateLanguageRepository:
    session: AsyncSession

    async def list_by_document_id(self, document_id: str) -> list[CandidateLanguage]:
        result = await self.session.execute(
            select(CandidateLanguage).where(CandidateLanguage.document_id == document_id)
        )
        return list(result.scalars().all())

    async def delete_by_document_id(self, document_id: str) -> None:
        await self.session.execute(
            delete(CandidateLanguage).where(CandidateLanguage.document_id == document_id)
        )

    async def create(self, **values) -> CandidateLanguage:
        item = CandidateLanguage(**values)
        self.session.add(item)
        await self.session.flush()
        await self.session.refresh(item)
        return item


@dataclass(slots=True)
class CandidateExperienceRepository:
    session: AsyncSession

    async def list_by_document_id(self, document_id: str) -> list[CandidateExperience]:
        result = await self.session.execute(
            select(CandidateExperience)
            .where(CandidateExperience.document_id == document_id)
            .order_by(CandidateExperience.position_order.asc())
        )
        return list(result.scalars().all())

    async def delete_by_document_id(self, document_id: str) -> None:
        await self.session.execute(
            delete(CandidateExperience).where(
                CandidateExperience.document_id == document_id
            )
        )

    async def create(self, **values) -> CandidateExperience:
        item = CandidateExperience(**values)
        self.session.add(item)
        await self.session.flush()
        await self.session.refresh(item)
        return item


@dataclass(slots=True)
class CandidateSkillRepository:
    session: AsyncSession

    async def list_by_document_id(self, document_id: str) -> list[CandidateSkill]:
        result = await self.session.execute(
            select(CandidateSkill).where(CandidateSkill.document_id == document_id)
        )
        return list(result.scalars().all())

    async def delete_by_document_id(self, document_id: str) -> None:
        await self.session.execute(
            delete(CandidateSkill).where(CandidateSkill.document_id == document_id)
        )

    async def create(self, **values) -> CandidateSkill:
        item = CandidateSkill(**values)
        self.session.add(item)
        await self.session.flush()
        await self.session.refresh(item)
        return item


@dataclass(slots=True)
class CandidateEducationRepository:
    session: AsyncSession

    async def list_by_document_id(self, document_id: str) -> list[CandidateEducation]:
        result = await self.session.execute(
            select(CandidateEducation)
            .where(CandidateEducation.document_id == document_id)
            .order_by(CandidateEducation.position_order.asc())
        )
        return list(result.scalars().all())

    async def delete_by_document_id(self, document_id: str) -> None:
        await self.session.execute(
            delete(CandidateEducation).where(
                CandidateEducation.document_id == document_id
            )
        )

    async def create(self, **values) -> CandidateEducation:
        item = CandidateEducation(**values)
        self.session.add(item)
        await self.session.flush()
        await self.session.refresh(item)
        return item


@dataclass(slots=True)
class CandidateCertificationRepository:
    session: AsyncSession

    async def list_by_document_id(
        self,
        document_id: str,
    ) -> list[CandidateCertification]:
        result = await self.session.execute(
            select(CandidateCertification).where(
                CandidateCertification.document_id == document_id
            )
        )
        return list(result.scalars().all())

    async def delete_by_document_id(self, document_id: str) -> None:
        await self.session.execute(
            delete(CandidateCertification).where(
                CandidateCertification.document_id == document_id
            )
        )

    async def create(self, **values) -> CandidateCertification:
        item = CandidateCertification(**values)
        self.session.add(item)
        await self.session.flush()
        await self.session.refresh(item)
        return item


@dataclass(slots=True)
class DocumentProcessingRunRepository:
    session: AsyncSession

    async def get_by_document_and_stage(
        self,
        document_id: str,
        processing_stage: ProcessingStage,
    ) -> DocumentProcessingRun | None:
        result = await self.session.execute(
            select(DocumentProcessingRun).where(
                DocumentProcessingRun.document_id == document_id,
                DocumentProcessingRun.processing_stage == processing_stage.value,
            )
        )
        return result.scalars().first()

    async def mark_started(
        self,
        *,
        document_id: str,
        candidate_id: str | None,
        processing_stage: ProcessingStage,
        pipeline_version: str,
        model_version: str | None,
    ) -> DocumentProcessingRun:
        run = await self.get_by_document_and_stage(document_id, processing_stage)
        now = datetime.now(timezone.utc)
        if run is None:
            run = DocumentProcessingRun(
                document_id=document_id,
                candidate_id=candidate_id,
                processing_stage=processing_stage.value,
                status=ProcessingRunStatus.STARTED.value,
                pipeline_version=pipeline_version,
                model_version=model_version,
                started_at=now,
                completed_at=None,
                error_message=None,
            )
            self.session.add(run)
        else:
            run.candidate_id = candidate_id
            run.status = ProcessingRunStatus.STARTED.value
            run.pipeline_version = pipeline_version
            run.model_version = model_version
            run.started_at = now
            run.completed_at = None
            run.error_message = None
            run.extraction_confidence = None
        await self.session.flush()
        await self.session.refresh(run)
        return run

    async def mark_completed(
        self,
        run: DocumentProcessingRun,
        *,
        extraction_confidence: float | None,
    ) -> DocumentProcessingRun:
        run.status = ProcessingRunStatus.COMPLETED.value
        run.extraction_confidence = extraction_confidence
        run.completed_at = datetime.now(timezone.utc)
        run.error_message = None
        await self.session.flush()
        await self.session.refresh(run)
        return run

    async def mark_failed(
        self,
        *,
        document_id: str,
        candidate_id: str | None,
        processing_stage: ProcessingStage,
        pipeline_version: str,
        model_version: str | None,
        error_message: str,
    ) -> DocumentProcessingRun:
        run = await self.get_by_document_and_stage(document_id, processing_stage)
        now = datetime.now(timezone.utc)
        if run is None:
            run = DocumentProcessingRun(
                document_id=document_id,
                candidate_id=candidate_id,
                processing_stage=processing_stage.value,
                status=ProcessingRunStatus.FAILED.value,
                pipeline_version=pipeline_version,
                model_version=model_version,
                error_message=error_message[:500],
                started_at=now,
                completed_at=now,
            )
            self.session.add(run)
        else:
            run.candidate_id = candidate_id
            run.status = ProcessingRunStatus.FAILED.value
            run.pipeline_version = pipeline_version
            run.model_version = model_version
            run.error_message = error_message[:500]
            run.completed_at = now
        await self.session.flush()
        await self.session.refresh(run)
        return run


@dataclass(slots=True)
class EntityNormalizationRepository:
    session: AsyncSession

    async def get_by_class_and_original_lookup(
        self,
        normalization_class: NormalizationClass,
        original_value_lookup: str,
    ) -> EntityNormalization | None:
        result = await self.session.execute(
            select(EntityNormalization).where(
                EntityNormalization.normalization_class == normalization_class.value,
                EntityNormalization.original_value_lookup == original_value_lookup,
            )
        )
        return result.scalars().first()

    async def list_canonical_values_by_class(
        self,
        normalization_class: NormalizationClass,
    ) -> list[str]:
        result = await self.session.execute(
            select(EntityNormalization.normalized_value_canonical).where(
                EntityNormalization.normalization_class == normalization_class.value,
                EntityNormalization.normalization_status
                == NormalizationStatus.NORMALIZED.value,
                EntityNormalization.normalized_value_canonical.is_not(None),
            )
        )
        values = [value for value in result.scalars().all() if value]
        return list(dict.fromkeys(values))

    async def list_by_class(
        self,
        normalization_class: NormalizationClass,
    ) -> list[EntityNormalization]:
        result = await self.session.execute(
            select(EntityNormalization)
            .where(EntityNormalization.normalization_class == normalization_class.value)
            .order_by(EntityNormalization.created_at.asc())
        )
        return list(result.scalars().all())

    async def upsert_normalization(
        self,
        *,
        normalization_class: NormalizationClass,
        original_value: str,
        original_value_lookup: str,
        normalized_value: str | None,
        normalized_value_canonical: str | None,
        normalization_status: NormalizationStatus,
        confidence: float | None,
        provider: str,
        model_version: str | None,
        pipeline_version: str | None,
        metadata_json: str | None,
    ) -> EntityNormalization:
        record = await self.get_by_class_and_original_lookup(
            normalization_class,
            original_value_lookup,
        )
        if record is None:
            record = EntityNormalization(
                normalization_class=normalization_class.value,
                original_value=original_value,
                original_value_lookup=original_value_lookup,
                normalized_value=normalized_value,
                normalized_value_canonical=normalized_value_canonical,
                normalization_status=normalization_status.value,
                confidence=confidence,
                provider=provider,
                model_version=model_version,
                pipeline_version=pipeline_version,
                metadata_json=metadata_json,
            )
            self.session.add(record)
        else:
            record.original_value = original_value
            record.normalized_value = normalized_value
            record.normalized_value_canonical = normalized_value_canonical
            record.normalization_status = normalization_status.value
            record.confidence = confidence
            record.provider = provider
            record.model_version = model_version
            record.pipeline_version = pipeline_version
            record.metadata_json = metadata_json
        await self.session.flush()
        await self.session.refresh(record)
        return record

@dataclass(slots=True)
class JobSearchProfileRepository:
    session: AsyncSession

    async def get_by_job_id(self, job_id: str) -> JobSearchProfile | None:
        result = await self.session.execute(
            select(JobSearchProfile).where(JobSearchProfile.job_id == job_id)
        )
        return result.scalars().first()

    async def delete_by_job_id(self, job_id: str) -> None:
        await self.session.execute(
            delete(JobSearchProfile).where(JobSearchProfile.job_id == job_id)
        )

    async def create(self, **values) -> JobSearchProfile:
        item = JobSearchProfile(**values)
        self.session.add(item)
        await self.session.flush()
        await self.session.refresh(item)
        return item


@dataclass(slots=True)
class JobRequiredLanguageRepository:
    session: AsyncSession

    async def list_by_profile_id(self, profile_id: str) -> list[JobRequiredLanguage]:
        result = await self.session.execute(
            select(JobRequiredLanguage)
            .where(JobRequiredLanguage.job_search_profile_id == profile_id)
            .order_by(JobRequiredLanguage.created_at.asc())
        )
        return list(result.scalars().all())

    async def delete_by_profile_id(self, profile_id: str) -> None:
        await self.session.execute(
            delete(JobRequiredLanguage).where(
                JobRequiredLanguage.job_search_profile_id == profile_id
            )
        )

    async def create(self, **values) -> JobRequiredLanguage:
        item = JobRequiredLanguage(**values)
        self.session.add(item)
        await self.session.flush()
        await self.session.refresh(item)
        return item


@dataclass(slots=True)
class JobRequiredSkillRepository:
    session: AsyncSession

    async def list_by_profile_id(self, profile_id: str) -> list[JobRequiredSkill]:
        result = await self.session.execute(
            select(JobRequiredSkill)
            .where(JobRequiredSkill.job_search_profile_id == profile_id)
            .order_by(JobRequiredSkill.created_at.asc())
        )
        return list(result.scalars().all())

    async def delete_by_profile_id(self, profile_id: str) -> None:
        await self.session.execute(
            delete(JobRequiredSkill).where(
                JobRequiredSkill.job_search_profile_id == profile_id
            )
        )

    async def create(self, **values) -> JobRequiredSkill:
        item = JobRequiredSkill(**values)
        self.session.add(item)
        await self.session.flush()
        await self.session.refresh(item)
        return item


@dataclass(slots=True)
class JobDomainRepository:
    session: AsyncSession

    async def list_by_profile_id(self, profile_id: str) -> list[JobDomain]:
        result = await self.session.execute(
            select(JobDomain)
            .where(JobDomain.job_search_profile_id == profile_id)
            .order_by(JobDomain.created_at.asc())
        )
        return list(result.scalars().all())

    async def delete_by_profile_id(self, profile_id: str) -> None:
        await self.session.execute(
            delete(JobDomain).where(JobDomain.job_search_profile_id == profile_id)
        )

    async def create(self, **values) -> JobDomain:
        item = JobDomain(**values)
        self.session.add(item)
        await self.session.flush()
        await self.session.refresh(item)
        return item


@dataclass(slots=True)
class JobProcessingRunRepository:
    session: AsyncSession

    async def get_by_job_and_stage(
        self,
        job_id: str,
        pipeline_stage: ProcessingStage,
    ) -> JobProcessingRun | None:
        result = await self.session.execute(
            select(JobProcessingRun).where(
                JobProcessingRun.job_id == job_id,
                JobProcessingRun.pipeline_stage == pipeline_stage.value,
            )
        )
        return result.scalars().first()

    async def mark_started(
        self,
        *,
        job_id: str,
        source_document_id: str | None,
        pipeline_stage: ProcessingStage,
        pipeline_version: str,
        model_version: str | None,
    ) -> JobProcessingRun:
        run = await self.get_by_job_and_stage(job_id, pipeline_stage)
        now = datetime.now(timezone.utc)
        if run is None:
            run = JobProcessingRun(
                job_id=job_id,
                source_document_id=source_document_id,
                pipeline_stage=pipeline_stage.value,
                status=ProcessingRunStatus.STARTED.value,
                pipeline_version=pipeline_version,
                model_version=model_version,
                started_at=now,
                finished_at=None,
                error_message=None,
            )
            self.session.add(run)
        else:
            run.source_document_id = source_document_id
            run.status = ProcessingRunStatus.STARTED.value
            run.pipeline_version = pipeline_version
            run.model_version = model_version
            run.started_at = now
            run.finished_at = None
            run.error_message = None
            run.extraction_confidence = None
        await self.session.flush()
        await self.session.refresh(run)
        return run

    async def mark_completed(
        self,
        run: JobProcessingRun,
        *,
        extraction_confidence: float | None,
    ) -> JobProcessingRun:
        run.status = ProcessingRunStatus.COMPLETED.value
        run.extraction_confidence = extraction_confidence
        run.finished_at = datetime.now(timezone.utc)
        run.error_message = None
        await self.session.flush()
        await self.session.refresh(run)
        return run

    async def mark_failed(
        self,
        *,
        job_id: str,
        source_document_id: str | None,
        pipeline_stage: ProcessingStage,
        pipeline_version: str,
        model_version: str | None,
        error_message: str,
    ) -> JobProcessingRun:
        run = await self.get_by_job_and_stage(job_id, pipeline_stage)
        now = datetime.now(timezone.utc)
        if run is None:
            run = JobProcessingRun(
                job_id=job_id,
                source_document_id=source_document_id,
                pipeline_stage=pipeline_stage.value,
                status=ProcessingRunStatus.FAILED.value,
                pipeline_version=pipeline_version,
                model_version=model_version,
                error_message=error_message[:500],
                started_at=now,
                finished_at=now,
            )
            self.session.add(run)
        else:
            run.source_document_id = source_document_id
            run.status = ProcessingRunStatus.FAILED.value
            run.pipeline_version = pipeline_version
            run.model_version = model_version
            run.error_message = error_message[:500]
            run.finished_at = now
        await self.session.flush()
        await self.session.refresh(run)
        return run
