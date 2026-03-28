from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.config.enums.document_status import DocumentProcessingStatus


class CandidateUpsertPayload(BaseModel):
    candidate_id: str | None = Field(
        default=None,
        description="Existing candidate identifier when upserting into a known candidate.",
    )
    external_id: str | None = Field(
        default=None,
        description="External system identifier for the candidate, if available.",
    )
    full_name: str | None = Field(
        default=None, description="Candidate full name supplied during upsert."
    )
    email: EmailStr | None = Field(
        default=None, description="Candidate email address supplied during upsert."
    )


class UploadDocumentResponse(BaseModel):
    document_id: str = Field(description="Created or reused document identifier.")
    candidate_id: str = Field(
        description="Candidate identifier associated with the uploaded document."
    )
    status: DocumentProcessingStatus = Field(
        description="Initial processing status after upload."
    )
    checksum_sha256: str = Field(description="SHA-256 checksum of the uploaded file.")
    duplicate: bool = Field(
        default=False,
        description="Whether the uploaded file was detected as a duplicate.",
    )
    pipeline_status_url: str | None = Field(
        default=None, description="Backend URL for polling pipeline status."
    )


class CandidateInfoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    candidate_id: str = Field(description="Candidate identifier.")
    external_id: str | None = Field(
        default=None, description="External candidate identifier, if any."
    )
    full_name: str | None = Field(default=None, description="Candidate full name.")
    email: EmailStr | None = Field(default=None, description="Candidate email address.")
    created_at: datetime = Field(description="Candidate record creation timestamp.")
    updated_at: datetime = Field(description="Candidate record last update timestamp.")


class DocumentStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    document_id: str = Field(description="Document identifier.")
    candidate_id: str = Field(
        description="Candidate identifier associated with the document."
    )
    original_filename: str = Field(description="Original uploaded filename.")
    file_extension: str = Field(description="Detected file extension.")
    content_type: str | None = Field(
        default=None, description="Detected MIME type of the uploaded document."
    )
    size_bytes: int = Field(description="Document size in bytes.")
    checksum_sha256: str = Field(description="SHA-256 checksum of the stored document.")
    processing_status: DocumentProcessingStatus = Field(
        description="Current document processing status."
    )
    indexing_status: str = Field(
        description="Current vector indexing status for the document."
    )
    extractor_name: str | None = Field(
        default=None,
        description="Raw text extraction strategy or provider used for the document.",
    )
    extracted_char_count: int | None = Field(
        default=None,
        description="Extracted character count for the document text, when available.",
    )
    text_available: bool = Field(
        description="Whether extracted text is currently available for the document."
    )
    error_message: str | None = Field(
        default=None, description="Last processing error message, if any."
    )
    created_at: datetime = Field(description="Document record creation timestamp.")
    updated_at: datetime = Field(description="Document record last update timestamp.")
    candidate: CandidateInfoResponse = Field(
        description="Candidate data associated with the document."
    )


class DocumentListResponse(BaseModel):
    total: int = Field(
        description="Total number of documents available before pagination."
    )
    items: list[DocumentStatusResponse] = Field(
        description="Document status items returned by the list endpoint."
    )


class ErrorResponse(BaseModel):
    detail: str = Field(..., examples=["Unsupported file type: txt"])


class PipelineStageStatusResponse(BaseModel):
    stage: str = Field(description="Pipeline stage name.")
    status: str = Field(description="Status for the pipeline stage.")
    pipeline_version: str | None = Field(
        default=None, description="Pipeline version used for the stage."
    )
    model_version: str | None = Field(
        default=None, description="Model version used for the stage, when relevant."
    )
    extraction_confidence: float | None = Field(
        default=None,
        description="Extraction confidence reported for the stage, when relevant.",
    )
    error_message: str | None = Field(
        default=None, description="Stage error message, if any."
    )
    started_at: datetime | None = Field(
        default=None, description="Timestamp when the stage started."
    )
    completed_at: datetime | None = Field(
        default=None, description="Timestamp when the stage completed."
    )


class DocumentPipelineStatusResponse(BaseModel):
    document_id: str = Field(description="Document identifier.")
    candidate_id: str = Field(
        description="Candidate identifier associated with the document."
    )
    processing_status: DocumentProcessingStatus = Field(
        description="Overall processing status for the document."
    )
    indexing_status: str = Field(
        description="Overall vector indexing status for the document."
    )
    current_stage: str = Field(description="Current pipeline stage name.")
    is_terminal: bool = Field(
        description="Whether the pipeline reached a terminal state."
    )
    text_available: bool = Field(
        description="Whether extracted text is available for the document."
    )
    storage_available: bool = Field(
        description="Whether the original uploaded file is available in storage."
    )
    error_message: str | None = Field(
        default=None, description="Latest pipeline error message, if any."
    )
    raw_text_extraction: PipelineStageStatusResponse | None = Field(
        default=None, description="Raw text extraction stage details."
    )
    entity_extraction: PipelineStageStatusResponse | None = Field(
        default=None, description="Entity extraction stage details."
    )
    vector_indexing: PipelineStageStatusResponse | None = Field(
        default=None, description="Vector indexing stage details."
    )
    updated_at: datetime = Field(
        description="Last update timestamp for the document pipeline status."
    )
