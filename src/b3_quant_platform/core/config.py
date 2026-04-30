from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="B3_",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "b3-ml-platform"
    environment: str = "local"
    api_prefix: str = "/v1"
    structured_log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8080
    database_url: str = "sqlite+pysqlite:///./data/local.db"
    allowed_origins: list[str] = Field(default_factory=lambda: ["http://localhost:8501"])

    r2_endpoint_url: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket: str = "b3-operational-lake"
    r2_region: str = "auto"

    gcs_bucket: str = "b3-analytics-mirror"
    bigquery_project_id: str = ""
    bigquery_dataset: str = "b3_analytics"
    bigquery_external_dataset: str = "raw_analytics"
    bigquery_native_dataset: str = "curated_analytics"
    biglake_connection_id: str = ""

    upstash_redis_rest_url: str = ""
    upstash_redis_rest_token: str = ""
    qstash_token: str = ""
    qstash_current_signing_key: str = ""
    qstash_next_signing_key: str = ""

    cloud_run_base_url: str = ""
    edge_shared_secret: str = ""

    default_market: str = "equities"
    tf_artifact_dir: Path = Path("./artifacts/models")
    local_parquet_dir: Path = Path("./artifacts/parquet")
    analytics_state_dir: Path = Path("./artifacts/state")

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def split_allowed_origins(cls, value: object) -> list[str]:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, list):
            return [str(item) for item in value]
        raise TypeError("allowed_origins must be a comma-separated string or list")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.tf_artifact_dir.mkdir(parents=True, exist_ok=True)
    settings.local_parquet_dir.mkdir(parents=True, exist_ok=True)
    settings.analytics_state_dir.mkdir(parents=True, exist_ok=True)
    return settings
