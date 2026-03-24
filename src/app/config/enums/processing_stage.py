from enum import StrEnum


class ProcessingStage(StrEnum):
    RAW_TEXT_EXTRACTION = "raw_text_extraction"
    ENTITY_EXTRACTION = "entity_extraction"
    VECTOR_INDEXING = "vector_indexing"
    JOB_SEARCH_PREPARATION = "job_search_preparation"
