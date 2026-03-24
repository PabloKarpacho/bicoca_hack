from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm_api_key: str | None = Field(default=None, alias="LLM_API_KEY")
    llm_base_url: str = Field(
        default="https://api.openai.com/v1",
        alias="LLM_BASE_URL",
    )
    llm_cv_extraction_model_name: str | None = Field(
        default=None,
        alias="LLM_CV_EXTRACTION_MODEL_NAME",
    )
    llm_job_search_preparation_model_name: str | None = Field(
        default=None,
        alias="LLM_JOB_SEARCH_PREPARATION_MODEL_NAME",
    )
    llm_entity_normalization_model_name: str | None = Field(
        default=None,
        alias="LLM_ENTITY_NORMALIZATION_MODEL_NAME",
    )
    llm_doc_summary_model_name: str | None = Field(
        default=None,
        alias="LLM_DOC_SUMMARY_MODEL_NAME",
    )
    embedding_model_name: str | None = Field(default=None, alias="EMBEDDING_MODEL_NAME")

    unstructured_api_key: str | None = Field(
        default=None,
        alias="UNSTRUCTURED_API_KEY",
    )
    default_vector_size: int = 1536


llm_settings = LLMSettings()
