from enum import StrEnum


class NormalizationStatus(StrEnum):
    NORMALIZED = "normalized"
    NO_MATCH = "no_match"
    NEEDS_REVIEW = "needs_review"
    FAILED = "failed"
