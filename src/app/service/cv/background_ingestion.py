from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.config.enums.document_status import DocumentProcessingStatus
from app.config.enums.processing_stage import ProcessingStage
from app.models.rag import NamedBuffer
from app.service.cv.entity_extraction.service import CandidateEntityExtractionService
from app.service.cv.storage import CVStorageService
from app.service.search.candidate_vector_indexing import (
    CandidateVectorIndexingError,
    CandidateVectorIndexingService,
)
from app.service.vector_db.qdrant.qdrant_api import QdrantAPI
from database.postgres.crud.cv import (
    CandidateCertificationRepository,
    CandidateDocumentChunkRepository,
    CandidateDocumentRepository,
    CandidateDocumentTextRepository,
    CandidateEducationRepository,
    CandidateExperienceRepository,
    CandidateLanguageRepository,
    CandidateProfileRepository,
    CandidateSkillRepository,
    DocumentProcessingRunRepository,
)

PIPELINE_VERSION = "resume_background_ingestion_v1"
RAW_TEXT_MODEL_VERSION = "unstructured"


class ResumeBackgroundIngestionError(RuntimeError):
    pass


@dataclass(slots=True)
class ResumeBackgroundIngestionService:
    sessionmaker: async_sessionmaker[AsyncSession]
    cv_storage: CVStorageService
    qdrant: QdrantAPI | None

    async def run(
        self,
        *,
        document_id: str,
        file_bytes: bytes,
        filename: str,
    ) -> None:
        logger.info(
            "Resume background ingestion: started for document_id={document_id}",
            document_id=document_id,
        )
        try:
            raw_text = await self._extract_raw_text(
                document_id=document_id,
                file_bytes=file_bytes,
                filename=filename,
            )
            await self._run_entity_extraction(document_id)
            await self._run_vector_indexing(document_id)
            await self._mark_document_ready(
                document_id=document_id,
                extracted_char_count=len(raw_text),
            )
            logger.info(
                "Resume background ingestion: completed for document_id={document_id}",
                document_id=document_id,
            )
        except Exception as exc:
            logger.exception(
                "Resume background ingestion: failed for document_id={document_id}, error={error}",
                document_id=document_id,
                error=str(exc),
            )
            await self._cleanup_failed_pipeline(
                document_id=document_id,
                error_message=str(exc),
            )

    async def _extract_raw_text(
        self,
        *,
        document_id: str,
        file_bytes: bytes,
        filename: str,
    ) -> str:
        try:
            from app.service.loaders.unstructured.unstructured_loader import (
                UnstructuredLoader,
            )
        except Exception as exc:
            await self._mark_raw_text_failed(
                document_id=document_id,
                error_message=f"Unstructured loader is unavailable: {exc}",
            )
            raise ResumeBackgroundIngestionError(
                f"Unstructured loader is unavailable: {exc}"
            ) from exc

        async with self.sessionmaker() as session:
            documents = CandidateDocumentRepository(session)
            document_texts = CandidateDocumentTextRepository(session)
            processing_runs = DocumentProcessingRunRepository(session)
            document = await documents.get_plain_by_id(document_id)
            if document is None:
                raise ResumeBackgroundIngestionError("Document not found")

            run = await processing_runs.mark_started(
                document_id=document_id,
                candidate_id=document.candidate_id,
                processing_stage=ProcessingStage.RAW_TEXT_EXTRACTION,
                pipeline_version=PIPELINE_VERSION,
                model_version=RAW_TEXT_MODEL_VERSION,
            )
            await documents.update_processing_status(
                document,
                status=DocumentProcessingStatus.EXTRACTING_TEXT,
                error_message=None,
            )
            await session.commit()

            try:
                contents = NamedBuffer(filename=filename, buf=BytesIO(file_bytes))
                loader = UnstructuredLoader(contents)
                parsed_chunks = await loader.load()
                raw_text = " ".join(
                    chunk.page_content.strip()
                    for chunk in parsed_chunks
                    if chunk.page_content and chunk.page_content.strip()
                ).strip()
                if not parsed_chunks or not raw_text:
                    raise ResumeBackgroundIngestionError(
                        "Uploaded file was parsed but no text was extracted"
                    )

                await document_texts.upsert(document_id=document_id, raw_text=raw_text)
                await documents.update_processing_status(
                    document,
                    status=DocumentProcessingStatus.RAW_TEXT_READY,
                    extractor_name=RAW_TEXT_MODEL_VERSION,
                    extracted_char_count=len(raw_text),
                    error_message=None,
                )
                await processing_runs.mark_completed(run, extraction_confidence=None)
                await session.commit()
                return raw_text
            except Exception as exc:
                await session.rollback()
                failed_message = (
                    str(exc)
                    if isinstance(exc, ResumeBackgroundIngestionError)
                    else f"Could not parse uploaded file: {exc}"
                )
                await self._mark_raw_text_failed(
                    document_id=document_id,
                    error_message=failed_message,
                )
                raise (
                    exc
                    if isinstance(exc, ResumeBackgroundIngestionError)
                    else ResumeBackgroundIngestionError(failed_message)
                ) from exc

    async def _mark_raw_text_failed(
        self,
        *,
        document_id: str,
        error_message: str,
    ) -> None:
        async with self.sessionmaker() as session:
            documents = CandidateDocumentRepository(session)
            processing_runs = DocumentProcessingRunRepository(session)
            document = await documents.get_plain_by_id(document_id)
            candidate_id = document.candidate_id if document else None
            await processing_runs.mark_failed(
                document_id=document_id,
                candidate_id=candidate_id,
                processing_stage=ProcessingStage.RAW_TEXT_EXTRACTION,
                pipeline_version=PIPELINE_VERSION,
                model_version=RAW_TEXT_MODEL_VERSION,
                error_message=error_message,
            )
            if document is not None:
                await documents.update_processing_status(
                    document,
                    status=DocumentProcessingStatus.FAILED,
                    extractor_name=None,
                    extracted_char_count=None,
                    error_message=error_message,
                )
            await session.commit()

    async def _run_entity_extraction(self, document_id: str) -> None:
        async with self.sessionmaker() as session:
            service = CandidateEntityExtractionService(session)
            await service.run(document_id)

    async def _run_vector_indexing(self, document_id: str) -> None:
        async with self.sessionmaker() as session:
            service = CandidateVectorIndexingService(
                session=session,
                qdrant=self.qdrant,
            )
            await service.index_document(document_id)

    async def _mark_document_ready(
        self,
        *,
        document_id: str,
        extracted_char_count: int,
    ) -> None:
        async with self.sessionmaker() as session:
            documents = CandidateDocumentRepository(session)
            document = await documents.get_plain_by_id(document_id)
            if document is None:
                return
            await documents.update_processing_status(
                document,
                status=DocumentProcessingStatus.READY,
                extractor_name=RAW_TEXT_MODEL_VERSION,
                extracted_char_count=extracted_char_count,
                error_message=None,
            )
            await documents.update_indexing_status(
                document,
                indexing_status="indexed",
                error_message=None,
            )
            await session.commit()

    async def _cleanup_failed_pipeline(
        self,
        *,
        document_id: str,
        error_message: str,
    ) -> None:
        cleanup_errors: list[str] = []
        storage_key: str | None = None
        storage_bucket: str | None = None

        async with self.sessionmaker() as session:
            documents = CandidateDocumentRepository(session)
            texts = CandidateDocumentTextRepository(session)
            profiles = CandidateProfileRepository(session)
            languages = CandidateLanguageRepository(session)
            experiences = CandidateExperienceRepository(session)
            skills = CandidateSkillRepository(session)
            education = CandidateEducationRepository(session)
            certifications = CandidateCertificationRepository(session)
            chunks = CandidateDocumentChunkRepository(session)

            document = await documents.get_plain_by_id(document_id)
            if document is None:
                return
            storage_key = document.storage_key
            storage_bucket = document.storage_bucket or self.cv_storage.bucket_name

            await texts.delete_by_document_id(document_id)
            await profiles.delete_by_document_id(document_id)
            await languages.delete_by_document_id(document_id)
            await experiences.delete_by_document_id(document_id)
            await skills.delete_by_document_id(document_id)
            await education.delete_by_document_id(document_id)
            await certifications.delete_by_document_id(document_id)
            await chunks.delete_by_document_id(document_id)

            document.processing_status = DocumentProcessingStatus.FAILED.value
            document.indexing_status = "failed"
            document.error_message = error_message[:500]
            document.extractor_name = None
            document.extracted_char_count = None
            document.storage_bucket = None
            document.storage_key = None
            await session.commit()

        if storage_key:
            try:
                await self.cv_storage.s3.delete_file(
                    key=storage_key,
                    bucket_name=storage_bucket or self.cv_storage.bucket_name,
                )
            except Exception as exc:
                cleanup_errors.append(f"s3_cleanup_failed={exc}")

        if self.qdrant is not None:
            try:
                await self.qdrant.delete_vectors_by_document_id(
                    settings.qdrant_candidate_chunks_collection_name,
                    document_id,
                )
            except Exception as exc:
                cleanup_errors.append(f"qdrant_cleanup_failed={exc}")

        if cleanup_errors:
            async with self.sessionmaker() as session:
                documents = CandidateDocumentRepository(session)
                document = await documents.get_plain_by_id(document_id)
                if document is None:
                    return
                document.error_message = (
                    f"{error_message[:350]} | cleanup: {'; '.join(cleanup_errors)}"
                )[:500]
                await session.commit()
