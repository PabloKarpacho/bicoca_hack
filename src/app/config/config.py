from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: str = "local"
    debug: bool = False
    docs_url: str | None = "/docs"
    redoc_url: str | None = "/redoc"
    origins: list[str] = Field(default_factory=lambda: ["*"])

    db_postgres_url_async: str = Field(alias="DB_POSTGRES_URL_ASYNC")
    db_postgres_url_sync: str = Field(alias="DB_POSTGRES_URL_SYNC")

    s3_access_key_id: str = Field(alias="S3_ROOT_USER")
    s3_secret_access_key: str = Field(alias="S3_ROOT_PASSWORD")
    s3_files_bucket_name: str = Field(alias="S3_FILES_BUCKET_NAME")
    s3_endpoint_url: str = Field(alias="S3_ENDPOINT")
    s3_region_name: str = "us-east-1"

    qdrant_url: str | None = Field(default=None, alias="QDRANT_URL")
    qdrant_candidate_chunks_collection_name: str = Field(
        default="candidate_chunks",
        alias="QDRANT_CANDIDATE_CHUNKS_COLLECTION_NAME",
    )
    hh_autosuggest_base_url: str = Field(
        default="https://hh.ru",
        alias="HH_AUTOSUGGEST_BASE_URL",
    )
    hh_autosuggest_timeout_seconds: int = Field(
        default=5,
        alias="HH_AUTOSUGGEST_TIMEOUT_SECONDS",
    )
    hh_autosuggest_enabled: bool = Field(
        default=True,
        alias="HH_AUTOSUGGEST_ENABLED",
    )
    hh_autosuggest_max_items_to_consider: int = Field(
        default=5,
        alias="HH_AUTOSUGGEST_MAX_ITEMS_TO_CONSIDER",
    )
    hh_autosuggest_min_confidence_threshold: float = Field(
        default=0.55,
        alias="HH_AUTOSUGGEST_MIN_CONFIDENCE_THRESHOLD",
    )
    hh_autosuggest_user_agent: str = Field(
        default="hack-cv-service/1.0",
        alias="HH_AUTOSUGGEST_USER_AGENT",
    )
    hh_autosuggest_cache_ttl_seconds: int = Field(
        default=1800,
        alias="HH_AUTOSUGGEST_CACHE_TTL_SECONDS",
    )

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug(cls, value):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"release", "prod", "production", "false", "0", "off"}:
                return False
            if normalized in {"debug", "dev", "true", "1", "on"}:
                return True
        return value


settings = Settings()
