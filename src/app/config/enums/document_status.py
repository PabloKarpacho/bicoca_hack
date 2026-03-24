from enum import StrEnum


class DocumentProcessingStatus(StrEnum):
    UPLOADED = "uploaded"
    STORED = "stored"
    EXTRACTING_TEXT = "extracting_text"
    RAW_TEXT_READY = "raw_text_ready"
    READY = "ready"
    FAILED = "failed"
