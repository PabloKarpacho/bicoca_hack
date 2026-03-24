from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.config.enums.document_status import DocumentProcessingStatus


class CandidateUpsertPayload(BaseModel):
    candidate_id: str | None = None
    external_id: str | None = None
    full_name: str | None = None
    email: EmailStr | None = None


class UploadDocumentResponse(BaseModel):
    document_id: str
    candidate_id: str
    status: DocumentProcessingStatus
    checksum_sha256: str
    duplicate: bool = False
    pipeline_status_url: str | None = None


class CandidateInfoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    candidate_id: str
    external_id: str | None = None
    full_name: str | None = None
    email: EmailStr | None = None
    created_at: datetime
    updated_at: datetime


class DocumentStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    document_id: str
    candidate_id: str
    original_filename: str
    file_extension: str
    content_type: str | None = None
    size_bytes: int
    checksum_sha256: str
    processing_status: DocumentProcessingStatus
    indexing_status: str
    extractor_name: str | None = None
    extracted_char_count: int | None = None
    text_available: bool
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    candidate: CandidateInfoResponse


class ErrorResponse(BaseModel):
    detail: str = Field(..., examples=["Unsupported file type: txt"])


class PipelineStageStatusResponse(BaseModel):
    stage: str
    status: str
    pipeline_version: str | None = None
    model_version: str | None = None
    extraction_confidence: float | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class DocumentPipelineStatusResponse(BaseModel):
    document_id: str
    candidate_id: str
    processing_status: DocumentProcessingStatus
    indexing_status: str
    current_stage: str
    is_terminal: bool
    text_available: bool
    storage_available: bool
    error_message: str | None = None
    raw_text_extraction: PipelineStageStatusResponse | None = None
    entity_extraction: PipelineStageStatusResponse | None = None
    vector_indexing: PipelineStageStatusResponse | None = None
    updated_at: datetime
