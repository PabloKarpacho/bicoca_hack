from __future__ import annotations

import json
from dataclasses import dataclass

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.config.enums.processing_stage import ProcessingStage
from app.models.candidate_vector import CandidateVectorIndexRunResponse
from app.service.search.candidate_chunk_builder import CandidateChunkBuilderService
from app.service.search.candidate_embedding_service import CandidateEmbeddingService
from app.service.vector_db.qdrant.qdrant_api import QdrantAPI
from database.postgres.crud.cv import (
    CandidateDocumentChunkRepository,
    CandidateDocumentRepository,
    CandidateExperienceRepository,
    CandidateLanguageRepository,
    CandidateProfileRepository,
    CandidateSkillRepository,
    DocumentProcessingRunRepository,
)

PIPELINE_VERSION = "candidate_vector_index_mvp_v1"


class CandidateVectorIndexingError(RuntimeError):
    pass


@dataclass
class CandidateVectorIndexingService:
    session: AsyncSession
    qdrant: QdrantAPI | None
    embedding_service: CandidateEmbeddingService | None = None
    collection_name: str = settings.qdrant_candidate_chunks_collection_name

    def __post_init__(self) -> None:
        self.documents = CandidateDocumentRepository(self.session)
        self.chunks = CandidateDocumentChunkRepository(self.session)
        self.processing_runs = DocumentProcessingRunRepository(self.session)
        self.embedding_service = self.embedding_service or CandidateEmbeddingService()
        self.chunk_builder = CandidateChunkBuilderService(
            profiles=CandidateProfileRepository(self.session),
            languages=CandidateLanguageRepository(self.session),
            experiences=CandidateExperienceRepository(self.session),
            skills=CandidateSkillRepository(self.session),
        )

    async def index_document(self, document_id: str) -> CandidateVectorIndexRunResponse:
        if self.qdrant is None:
            raise CandidateVectorIndexingError("Qdrant is not configured")

        document = await self.documents.get_plain_by_id(document_id)
        if document is None:
            raise CandidateVectorIndexingError("Document not found")
        candidate_id = document.candidate_id

        run = await self.processing_runs.mark_started(
            document_id=document_id,
            candidate_id=candidate_id,
            processing_stage=ProcessingStage.VECTOR_INDEXING,
            pipeline_version=PIPELINE_VERSION,
            model_version=self.embedding_service.model_version,
        )
        await self.documents.update_indexing_status(
            document,
            indexing_status="started",
            error_message=None,
        )
        await self.session.commit()

        try:
            drafts = await self.chunk_builder.build_document_chunks(document_id)
            existing_chunks = await self.chunks.list_by_document_id(document_id)
            logger.info(
                "Candidate vector indexing: built chunks for document_id={document_id}, chunk_count={chunk_count}",
                document_id=document_id,
                chunk_count=len(drafts),
            )

            existing_by_hash = {chunk.chunk_hash: chunk for chunk in existing_chunks}
            next_hashes = {draft.chunk_hash for draft in drafts}
            stale_chunks = [
                chunk for chunk in existing_chunks if chunk.chunk_hash not in next_hashes
            ]

            rows_needing_embedding = []

            for draft in drafts:
                existing = existing_by_hash.get(draft.chunk_hash)
                if existing is None:
                    row = await self.chunks.create(
                        candidate_id=draft.candidate_id,
                        document_id=draft.document_id,
                        chunk_type=draft.chunk_type,
                        chunk_text=draft.chunk_text,
                        chunk_hash=draft.chunk_hash,
                        source_entity_type=draft.source_entity_type,
                        source_entity_id=draft.source_entity_id,
                        chunk_metadata_json=json.dumps(
                            draft.chunk_metadata,
                            ensure_ascii=False,
                            sort_keys=True,
                        ),
                        embedding_status="pending",
                        embedding_model_version=self.embedding_service.model_version,
                        qdrant_point_id=None,
                    )
                    rows_needing_embedding.append((row, draft))
                    continue

                existing.chunk_metadata_json = json.dumps(
                    draft.chunk_metadata,
                    ensure_ascii=False,
                    sort_keys=True,
                )
                existing.chunk_text = draft.chunk_text
                existing.chunk_type = draft.chunk_type
                existing.source_entity_type = draft.source_entity_type
                existing.source_entity_id = draft.source_entity_id

                if self._can_reuse_chunk(existing):
                    await self.chunks.mark_reused(
                        existing,
                        embedding_model_version=self.embedding_service.model_version,
                    )
                    continue

                rows_needing_embedding.append((existing, draft))

            if stale_chunks:
                try:
                    await self.qdrant.delete_points_by_ids(
                        self.collection_name,
                        [chunk.chunk_id for chunk in stale_chunks],
                    )
                except ValueError:
                    pass
                await self.chunks.delete_by_chunk_ids(
                    [chunk.chunk_id for chunk in stale_chunks]
                )

            vectors = await self.embedding_service.embed_texts(
                [draft.chunk_text for _, draft in rows_needing_embedding]
            )
            if rows_needing_embedding and len(vectors) != len(rows_needing_embedding):
                raise CandidateVectorIndexingError(
                    "Embedding provider returned unexpected vector count"
                )

            if vectors:
                await self.qdrant.create_collection(
                    collection_name=self.collection_name,
                    vector_size=len(vectors[0]),
                )
                points = [
                    {
                        "id": chunk.chunk_id,
                        "vector": vector,
                        "payload": self._build_qdrant_payload(
                            chunk=chunk,
                            metadata=draft.chunk_metadata,
                        ),
                    }
                    for (chunk, draft), vector in zip(rows_needing_embedding, vectors)
                ]
                await self.qdrant.upsert_points(
                    collection_name=self.collection_name,
                    points=points,
                )
                for chunk, _ in rows_needing_embedding:
                    await self.chunks.update_indexing(
                        chunk,
                        embedding_status="indexed",
                        embedding_model_version=self.embedding_service.model_version,
                        qdrant_point_id=chunk.chunk_id,
                    )

            await self.documents.update_indexing_status(
                document,
                indexing_status="indexed",
                error_message=None,
            )
            await self.processing_runs.mark_completed(
                run,
                extraction_confidence=None,
            )
            await self.session.commit()
            return CandidateVectorIndexRunResponse(
                document_id=document_id,
                candidate_id=candidate_id,
                status=run.status,
                pipeline_version=run.pipeline_version,
                embedding_model_version=run.model_version,
                chunk_count=len(drafts),
                collection_name=self.collection_name,
            )
        except Exception as exc:
            await self.session.rollback()
            await self.processing_runs.mark_failed(
                document_id=document_id,
                candidate_id=candidate_id,
                processing_stage=ProcessingStage.VECTOR_INDEXING,
                pipeline_version=PIPELINE_VERSION,
                model_version=self.embedding_service.model_version,
                error_message=str(exc),
            )
            document = await self.documents.get_plain_by_id(document_id)
            if document is not None:
                await self.documents.update_indexing_status(
                    document,
                    indexing_status="failed",
                    error_message=str(exc),
                )
            await self.session.commit()
            if isinstance(exc, CandidateVectorIndexingError):
                raise
            raise CandidateVectorIndexingError(str(exc)) from exc

    def _build_qdrant_payload(self, *, chunk, metadata: dict) -> dict:
        payload = {
            "candidate_id": chunk.candidate_id,
            "document_id": chunk.document_id,
            "chunk_id": chunk.chunk_id,
            "chunk_type": chunk.chunk_type,
            "text": chunk.chunk_text,
            "embedding_model_version": self.embedding_service.model_version,
        }
        for key in [
            "current_title_normalized",
            "profession_tags",
            "seniority_normalized",
            "skill_tags",
            "explicit_skill_tags",
            "experience_confirmed_skill_tags",
            "language_tags",
            "domain_tags",
            "company_name",
            "job_title_normalized",
            "is_current_role",
            "start_date",
            "end_date",
            "duration_months",
            "total_experience_months",
            "source_confidence",
        ]:
            if key in metadata and metadata[key] is not None:
                payload[key] = metadata[key]
        return payload

    def _can_reuse_chunk(self, chunk) -> bool:
        return (
            chunk.embedding_status == "indexed"
            and chunk.embedding_model_version == self.embedding_service.model_version
            and bool(chunk.qdrant_point_id)
        )
