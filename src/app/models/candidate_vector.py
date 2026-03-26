from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.common_types import VectorChunkTypeLiteral


class CandidateDocumentChunkData(BaseModel):
    candidate_id: str = Field(description="Candidate identifier that owns the chunk.")
    document_id: str = Field(description="Document identifier the chunk was built from.")
    chunk_type: VectorChunkTypeLiteral = Field(
        description="Canonical chunk type used for vector indexing and retrieval.",
    )
    chunk_text: str = Field(description="Final text content sent to the embedding model.")
    chunk_hash: str = Field(description="Deterministic hash of the chunk content used for reuse detection.")
    source_entity_type: str | None = Field(
        default=None,
        description="Optional source entity type that produced the chunk, for example profile or experience.",
    )
    source_entity_id: str | None = Field(
        default=None,
        description="Optional source entity identifier that produced the chunk.",
    )
    chunk_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured metadata attached to the chunk before indexing.",
    )


class CandidateVectorIndexRunResponse(BaseModel):
    document_id: str = Field(description="Document identifier processed by vector indexing.")
    candidate_id: str = Field(description="Candidate identifier associated with the indexed document.")
    status: str = Field(description="Vector indexing status.")
    pipeline_version: str = Field(description="Pipeline version used during vector indexing.")
    embedding_model_version: str | None = Field(
        default=None,
        description="Embedding model version used to produce chunk vectors.",
    )
    chunk_count: int = Field(description="Number of chunks indexed for the document.")
    collection_name: str = Field(description="Qdrant collection name used for the index.")


class CandidateVectorDebugHit(BaseModel):
    point_id: str = Field(description="Qdrant point identifier returned by debug search.")
    score: float = Field(description="Raw vector similarity score returned for the hit.")
    candidate_id: str | None = Field(default=None, description="Candidate identifier attached to the hit payload.")
    document_id: str | None = Field(default=None, description="Document identifier attached to the hit payload.")
    chunk_id: str | None = Field(default=None, description="Chunk identifier attached to the hit payload.")
    chunk_type: VectorChunkTypeLiteral | None = Field(
        default=None,
        description="Canonical chunk type attached to the hit payload.",
    )
    text_preview: str | None = Field(default=None, description="Short text preview for the hit.")
    payload: dict[str, Any] = Field(default_factory=dict, description="Raw payload returned by Qdrant for the hit.")


class CandidateVectorDebugSearchRequest(BaseModel):
    query_text: str = Field(min_length=1, description="Raw text that should be embedded and searched against the vector index.")


class CandidateVectorDebugSearchResponse(BaseModel):
    query_text: str = Field(description="Original query text used for the debug vector search.")
    vector_dimension: int = Field(description="Dimension of the generated query embedding.")
    collection_name: str = Field(description="Qdrant collection searched during the debug request.")
    distance_metric: str | None = Field(default=None, description="Distance metric configured for the collection.")
    chunk_types: list[VectorChunkTypeLiteral] | None = Field(
        default=None,
        description="Chunk types included in the debug search request, if constrained.",
    )
    score_threshold: float = Field(description="Minimum score threshold applied to debug hits.")
    hits: list[CandidateVectorDebugHit] = Field(description="Raw vector hits returned for the debug search.")
