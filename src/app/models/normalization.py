from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.config.enums.normalization_class import NormalizationClass
from app.config.enums.normalization_status import NormalizationStatus


class NormalizationAgentOutput(BaseModel):
    normalized_value: str | None = Field(default=None, description="Normalized value proposed by the agent.")
    status: NormalizationStatus = Field(description="Outcome status returned by the normalization agent.")
    confidence: float | None = Field(default=None, description="Confidence score for the agent normalization result.")
    rationale_short: str | None = Field(
        default=None,
        description="Short explanation of why the normalized value was selected.",
    )
    matched_existing_canonical: bool = Field(
        default=False,
        description="Whether the agent matched an already known canonical value.",
    )


class EntityNormalizationResult(BaseModel):
    original_value: str = Field(description="Original input value submitted for normalization.")
    normalization_class: NormalizationClass = Field(description="Normalization class used for the request.")
    normalized_value: str | None = Field(default=None, description="Normalized value returned by the pipeline.")
    normalized_value_canonical: str | None = Field(
        default=None,
        description="Canonical normalized value when canonicalization is available.",
    )
    status: NormalizationStatus = Field(description="Final normalization status.")
    provider: str = Field(description="Provider or strategy that produced the normalization result.")
    confidence: float | None = Field(default=None, description="Confidence score for the normalization result.")
    was_cache_hit: bool = Field(default=False, description="Whether the result was served from the normalization cache.")
    model_version: str | None = Field(default=None, description="Model version used by the provider, when applicable.")
    pipeline_version: str | None = Field(default=None, description="Pipeline version that produced the result.")
    metadata: dict[str, Any] | None = Field(default=None, description="Additional provider-specific metadata for the result.")


class EntityNormalizationRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    entity_normalization_id: str = Field(description="Normalization record identifier.")
    normalization_class: str = Field(description="Normalization class stored for the record.")
    original_value: str = Field(description="Original value stored for the normalization record.")
    original_value_lookup: str = Field(description="Lookup-normalized key used for deduplication and cache hits.")
    normalized_value: str | None = Field(default=None, description="Normalized value stored in the record.")
    normalized_value_canonical: str | None = Field(default=None, description="Canonical normalized value stored in the record.")
    normalization_status: str = Field(description="Normalization status stored in the record.")
    confidence: float | None = Field(default=None, description="Stored normalization confidence.")
    provider: str = Field(description="Provider that produced the stored normalization result.")
    model_version: str | None = Field(default=None, description="Model version used for the stored normalization result.")
    pipeline_version: str | None = Field(default=None, description="Pipeline version used for the stored normalization result.")
    metadata_json: str | None = Field(default=None, description="Serialized metadata stored with the normalization record.")
    created_at: datetime = Field(description="Normalization record creation timestamp.")
    updated_at: datetime = Field(description="Normalization record last update timestamp.")
