from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CandidateDocumentChunkData(BaseModel):
    candidate_id: str
    document_id: str
    chunk_type: str
    chunk_text: str
    chunk_hash: str
    source_entity_type: str | None = None
    source_entity_id: str | None = None
    chunk_metadata: dict[str, Any] = Field(default_factory=dict)


class CandidateVectorIndexRunResponse(BaseModel):
    document_id: str
    candidate_id: str
    status: str
    pipeline_version: str
    embedding_model_version: str | None = None
    chunk_count: int
    collection_name: str


class CandidateVectorSearchTopChunk(BaseModel):
    chunk_id: str
    document_id: str
    chunk_type: str
    score: float
    text_preview: str


class CandidateChunkRecordResponse(BaseModel):
    chunk_id: str
    candidate_id: str
    document_id: str
    chunk_type: str
    chunk_text: str
    chunk_hash: str
    source_entity_type: str | None = None
    source_entity_id: str | None = None
    embedding_status: str
    embedding_model_version: str | None = None
    qdrant_point_id: str | None = None
    chunk_metadata_json: str | None = None
    created_at: datetime
    updated_at: datetime


class CandidateVectorDebugHit(BaseModel):
    point_id: str
    score: float
    candidate_id: str | None = None
    document_id: str | None = None
    chunk_id: str | None = None
    chunk_type: str | None = None
    text_preview: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class CandidateVectorDebugSearchRequest(BaseModel):
    query_text: str = Field(min_length=1)


class CandidateVectorDebugSearchResponse(BaseModel):
    query_text: str
    vector_dimension: int
    collection_name: str
    distance_metric: str | None = None
    chunk_types: list[str] | None = None
    score_threshold: float
    hits: list[CandidateVectorDebugHit]
