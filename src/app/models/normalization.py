from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.config.enums.normalization_class import NormalizationClass
from app.config.enums.normalization_status import NormalizationStatus


class NormalizationAgentOutput(BaseModel):
    normalized_value: str | None = None
    status: NormalizationStatus
    confidence: float | None = None
    rationale_short: str | None = None
    matched_existing_canonical: bool = False


class EntityNormalizationResult(BaseModel):
    original_value: str
    normalization_class: NormalizationClass
    normalized_value: str | None = None
    normalized_value_canonical: str | None = None
    status: NormalizationStatus
    provider: str
    confidence: float | None = None
    was_cache_hit: bool = False
    model_version: str | None = None
    pipeline_version: str | None = None
    metadata: dict[str, Any] | None = None


class EntityNormalizationRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    entity_normalization_id: str
    normalization_class: str
    original_value: str
    original_value_lookup: str
    normalized_value: str | None = None
    normalized_value_canonical: str | None = None
    normalization_status: str
    confidence: float | None = None
    provider: str
    model_version: str | None = None
    pipeline_version: str | None = None
    metadata_json: str | None = None
    created_at: datetime
    updated_at: datetime
