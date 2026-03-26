import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    Float,
    ForeignKey,
    Integer,
    Index,
    String,
    TIMESTAMP,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.enums.document_status import DocumentProcessingStatus

Base = declarative_base()


class Candidate(Base):
    """Stores candidate identity data used to group uploaded CV documents."""

    __tablename__ = "candidates"
    __table_args__ = (
        Index("idx_candidate_external_id", "external_id"),
        Index("idx_candidate_email", "email"),
        Index("idx_candidate_created_at", "created_at"),
    )

    candidate_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    external_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    documents: Mapped[list["CandidateDocument"]] = relationship(
        "CandidateDocument",
        back_populates="candidate",
        cascade="all, delete-orphan",
    )


class CandidateDocument(Base):
    """Stores metadata and processing state for an uploaded candidate CV file."""

    __tablename__ = "candidate_documents"
    __table_args__ = (
        Index("idx_candidate_document_candidate_id", "candidate_id"),
        Index("idx_candidate_document_checksum", "checksum_sha256"),
        Index("idx_candidate_document_status", "processing_status"),
        UniqueConstraint(
            "candidate_id",
            "checksum_sha256",
            name="uq_candidate_document_candidate_checksum",
        ),
    )

    document_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    candidate_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("candidates.candidate_id", ondelete="CASCADE"),
        nullable=False,
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_extension: Mapped[str] = mapped_column(String(20), nullable=False)
    content_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger(), nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_bucket: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    storage_key: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    processing_status: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        default=DocumentProcessingStatus.UPLOADED.value,
    )
    indexing_status: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        default="pending",
    )
    extractor_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    extracted_char_count: Mapped[Optional[int]] = mapped_column(
        BigInteger(), nullable=True
    )
    error_message: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    candidate: Mapped["Candidate"] = relationship(
        "Candidate",
        back_populates="documents",
    )
    text: Mapped[Optional["CandidateDocumentText"]] = relationship(
        "CandidateDocumentText",
        back_populates="document",
        cascade="all, delete-orphan",
        uselist=False,
    )


class CandidateDocumentText(Base):
    """Stores raw extracted text for a processed candidate document."""

    __tablename__ = "candidate_document_texts"
    __table_args__ = (
        UniqueConstraint("document_id", name="uq_candidate_document_text_document_id"),
    )

    document_text_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("candidate_documents.document_id", ondelete="CASCADE"),
        nullable=False,
    )
    raw_text: Mapped[str] = mapped_column(Text(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    document: Mapped["CandidateDocument"] = relationship(
        "CandidateDocument",
        back_populates="text",
    )

class CandidateProfile(Base):
    """Stores normalized candidate profile fields extracted from one CV document."""

    __tablename__ = "candidate_profiles"
    __table_args__ = (
        Index("idx_candidate_profile_candidate_id", "candidate_id"),
        Index("idx_candidate_profile_current_title", "current_title_normalized"),
        Index("idx_candidate_profile_seniority", "seniority_normalized"),
        Index("idx_candidate_profile_total_experience", "total_experience_months"),
        UniqueConstraint("document_id", name="uq_candidate_profile_document_id"),
    )

    profile_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    candidate_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("candidates.candidate_id", ondelete="CASCADE"),
        nullable=False,
    )
    document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("candidate_documents.document_id", ondelete="CASCADE"),
        nullable=False,
    )
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    location_raw: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    linkedin_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    github_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    portfolio_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    headline: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    current_title_raw: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    current_title_normalized: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    seniority_normalized: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    remote_policies_json: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    employment_types_json: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    total_experience_months: Mapped[Optional[int]] = mapped_column(
        Integer(), nullable=True
    )
    extraction_confidence: Mapped[Optional[float]] = mapped_column(
        Float(), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class CandidateLanguage(Base):
    """Stores normalized language records extracted from one CV document."""

    __tablename__ = "candidate_languages"
    __table_args__ = (
        Index("idx_candidate_language_document_id", "document_id"),
        Index("idx_candidate_language_candidate_id", "candidate_id"),
        Index("idx_candidate_language_name", "language_normalized"),
        Index("idx_candidate_language_proficiency", "proficiency_normalized"),
    )

    language_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    candidate_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("candidates.candidate_id", ondelete="CASCADE"),
        nullable=False,
    )
    document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("candidate_documents.document_id", ondelete="CASCADE"),
        nullable=False,
    )
    language_raw: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    language_normalized: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    proficiency_raw: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    proficiency_normalized: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    confidence: Mapped[Optional[float]] = mapped_column(Float(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class CandidateExperience(Base):
    """Stores normalized work experience records extracted from one CV document."""

    __tablename__ = "candidate_experiences"
    __table_args__ = (
        Index("idx_candidate_experience_document_id", "document_id"),
        Index("idx_candidate_experience_candidate_id", "candidate_id"),
        Index("idx_candidate_experience_title", "job_title_normalized"),
        Index("idx_candidate_experience_domain", "domain_hint"),
    )

    experience_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    candidate_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("candidates.candidate_id", ondelete="CASCADE"),
        nullable=False,
    )
    document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("candidate_documents.document_id", ondelete="CASCADE"),
        nullable=False,
    )
    position_order: Mapped[int] = mapped_column(Integer(), nullable=False, default=1)
    company_name_raw: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    job_title_raw: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    job_title_normalized: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    start_date: Mapped[Optional[date]] = mapped_column(Date(), nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date(), nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean(), nullable=False, default=False)
    duration_months: Mapped[Optional[int]] = mapped_column(Integer(), nullable=True)
    location_raw: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    responsibilities_text: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    technologies_text: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    domain_hint: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class CandidateSkill(Base):
    """Stores normalized skill records extracted from one CV document."""

    __tablename__ = "candidate_skills"
    __table_args__ = (
        Index("idx_candidate_skill_document_id", "document_id"),
        Index("idx_candidate_skill_candidate_id", "candidate_id"),
        Index("idx_candidate_skill_name", "normalized_skill"),
    )

    skill_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    candidate_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("candidates.candidate_id", ondelete="CASCADE"),
        nullable=False,
    )
    document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("candidate_documents.document_id", ondelete="CASCADE"),
        nullable=False,
    )
    raw_skill: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    normalized_skill: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    skill_category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    source_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float(), nullable=True)
    normalization_source: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )
    normalization_external_id: Mapped[Optional[int]] = mapped_column(
        BigInteger(), nullable=True
    )
    normalization_status: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )
    normalization_confidence: Mapped[Optional[float]] = mapped_column(
        Float(), nullable=True
    )
    normalization_metadata_json: Mapped[Optional[str]] = mapped_column(
        Text(), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class CandidateEducation(Base):
    """Stores normalized education records extracted from one CV document."""

    __tablename__ = "candidate_education"
    __table_args__ = (
        Index("idx_candidate_education_document_id", "document_id"),
        Index("idx_candidate_education_candidate_id", "candidate_id"),
        Index("idx_candidate_education_degree", "degree_normalized"),
    )

    education_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    candidate_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("candidates.candidate_id", ondelete="CASCADE"),
        nullable=False,
    )
    document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("candidate_documents.document_id", ondelete="CASCADE"),
        nullable=False,
    )
    position_order: Mapped[int] = mapped_column(Integer(), nullable=False, default=1)
    institution_raw: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    degree_raw: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    degree_normalized: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    field_of_study: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    start_date: Mapped[Optional[date]] = mapped_column(Date(), nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date(), nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class CandidateCertification(Base):
    """Stores normalized certification records extracted from one CV document."""

    __tablename__ = "candidate_certifications"
    __table_args__ = (
        Index("idx_candidate_certification_document_id", "document_id"),
        Index("idx_candidate_certification_candidate_id", "candidate_id"),
        Index("idx_candidate_certification_name", "certification_name_normalized"),
    )

    certification_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    candidate_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("candidates.candidate_id", ondelete="CASCADE"),
        nullable=False,
    )
    document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("candidate_documents.document_id", ondelete="CASCADE"),
        nullable=False,
    )
    certification_name_raw: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    certification_name_normalized: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    issuer: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    issue_date: Mapped[Optional[date]] = mapped_column(Date(), nullable=True)
    expiry_date: Mapped[Optional[date]] = mapped_column(Date(), nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class CandidateDocumentChunk(Base):
    """Stores vectorizable candidate chunks persisted before Qdrant indexing."""

    __tablename__ = "candidate_document_chunks"
    __table_args__ = (
        Index("idx_candidate_chunk_document_id", "document_id"),
        Index("idx_candidate_chunk_candidate_id", "candidate_id"),
        Index("idx_candidate_chunk_type", "chunk_type"),
        Index("idx_candidate_chunk_embedding_status", "embedding_status"),
        UniqueConstraint(
            "document_id",
            "chunk_hash",
            name="uq_candidate_chunk_document_hash",
        ),
    )

    chunk_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    candidate_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("candidates.candidate_id", ondelete="CASCADE"),
        nullable=False,
    )
    document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("candidate_documents.document_id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_type: Mapped[str] = mapped_column(String(100), nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text(), nullable=False)
    chunk_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_entity_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    source_entity_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    chunk_metadata_json: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    embedding_status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    embedding_model_version: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    qdrant_point_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class DocumentProcessingRun(Base):
    """Stores the current pipeline run state for a document processing stage."""

    __tablename__ = "document_processing_runs"
    __table_args__ = (
        Index("idx_document_processing_run_document_id", "document_id"),
        Index("idx_document_processing_run_candidate_id", "candidate_id"),
        Index("idx_document_processing_run_stage", "processing_stage"),
        Index("idx_document_processing_run_status", "status"),
        UniqueConstraint(
            "document_id",
            "processing_stage",
            name="uq_document_processing_run_document_stage",
        ),
    )

    processing_run_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("candidate_documents.document_id", ondelete="CASCADE"),
        nullable=False,
    )
    candidate_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("candidates.candidate_id", ondelete="CASCADE"),
        nullable=True,
    )
    processing_stage: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(100), nullable=False)
    pipeline_version: Mapped[str] = mapped_column(String(100), nullable=False)
    model_version: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    extraction_confidence: Mapped[Optional[float]] = mapped_column(
        Float(), nullable=True
    )
    error_message: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class EntityNormalization(Base):
    """Stores reusable original-to-normalized mappings for all normalization classes."""

    __tablename__ = "entity_normalizations"
    __table_args__ = (
        Index("idx_entity_normalization_class", "normalization_class"),
        Index("idx_entity_normalization_status", "normalization_status"),
        UniqueConstraint(
            "normalization_class",
            "original_value_lookup",
            name="uq_entity_normalization_class_lookup",
        ),
    )

    entity_normalization_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    normalization_class: Mapped[str] = mapped_column(String(100), nullable=False)
    original_value: Mapped[str] = mapped_column(String(255), nullable=False)
    original_value_lookup: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_value: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    normalized_value_canonical: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    normalization_status: Mapped[str] = mapped_column(String(50), nullable=False)
    confidence: Mapped[Optional[float]] = mapped_column(Float(), nullable=True)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    model_version: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    pipeline_version: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class JobSearchProfile(Base):
    """Stores a search-ready vacancy representation derived from job description text."""

    __tablename__ = "job_search_profiles"
    __table_args__ = (
        Index("idx_job_search_profile_job_id", "job_id"),
        Index("idx_job_search_profile_title", "normalized_title"),
        Index("idx_job_search_profile_seniority", "seniority_normalized"),
        UniqueConstraint("job_id", name="uq_job_search_profile_job_id"),
    )

    job_search_profile_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    job_id: Mapped[str] = mapped_column(String(100), nullable=False)
    source_document_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    raw_title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    normalized_title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    seniority_normalized: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    location_raw: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    location_normalized: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    remote_policy: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    remote_policies_json: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    employment_types_json: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    employment_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    min_experience_months: Mapped[Optional[int]] = mapped_column(
        Integer(), nullable=True
    )
    education_requirements: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    certification_requirements: Mapped[Optional[str]] = mapped_column(
        Text(), nullable=True
    )
    semantic_query_text_main: Mapped[str] = mapped_column(Text(), nullable=False)
    semantic_query_text_responsibilities: Mapped[Optional[str]] = mapped_column(
        Text(), nullable=True
    )
    semantic_query_text_skills: Mapped[Optional[str]] = mapped_column(
        Text(), nullable=True
    )
    extraction_confidence: Mapped[Optional[float]] = mapped_column(
        Float(), nullable=True
    )
    pipeline_version: Mapped[str] = mapped_column(String(100), nullable=False)
    model_version: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class JobRequiredLanguage(Base):
    """Stores normalized language requirements extracted for a vacancy."""

    __tablename__ = "job_required_languages"
    __table_args__ = (
        Index("idx_job_required_language_profile_id", "job_search_profile_id"),
        Index("idx_job_required_language_name", "language_normalized"),
    )

    job_required_language_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    job_search_profile_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("job_search_profiles.job_search_profile_id", ondelete="CASCADE"),
        nullable=False,
    )
    language_normalized: Mapped[str] = mapped_column(String(255), nullable=False)
    min_proficiency_normalized: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    is_required: Mapped[bool] = mapped_column(Boolean(), nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class JobRequiredSkill(Base):
    """Stores normalized must-have and nice-to-have skill requirements for a vacancy."""

    __tablename__ = "job_required_skills"
    __table_args__ = (
        Index("idx_job_required_skill_profile_id", "job_search_profile_id"),
        Index("idx_job_required_skill_name", "normalized_skill"),
    )

    job_required_skill_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    job_search_profile_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("job_search_profiles.job_search_profile_id", ondelete="CASCADE"),
        nullable=False,
    )
    normalized_skill: Mapped[str] = mapped_column(String(255), nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean(), nullable=False, default=True)
    source_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class JobDomain(Base):
    """Stores normalized domain hints extracted from a vacancy."""

    __tablename__ = "job_domains"
    __table_args__ = (
        Index("idx_job_domain_profile_id", "job_search_profile_id"),
        Index("idx_job_domain_name", "domain_normalized"),
    )

    job_domain_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    job_search_profile_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("job_search_profiles.job_search_profile_id", ondelete="CASCADE"),
        nullable=False,
    )
    domain_normalized: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class JobProcessingRun(Base):
    """Stores the current vacancy preparation run state for one job and pipeline stage."""

    __tablename__ = "job_processing_runs"
    __table_args__ = (
        Index("idx_job_processing_run_job_id", "job_id"),
        Index("idx_job_processing_run_stage", "pipeline_stage"),
        Index("idx_job_processing_run_status", "status"),
        UniqueConstraint("job_id", "pipeline_stage", name="uq_job_processing_run_job_stage"),
    )

    job_processing_run_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    job_id: Mapped[str] = mapped_column(String(100), nullable=False)
    source_document_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    pipeline_stage: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(100), nullable=False)
    pipeline_version: Mapped[str] = mapped_column(String(100), nullable=False)
    model_version: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    extraction_confidence: Mapped[Optional[float]] = mapped_column(
        Float(), nullable=True
    )
    error_message: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
