from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from b3_quant_platform.core.config import Settings
from b3_quant_platform.models.base import Base


@pytest.fixture()
def test_settings(tmp_path: Path) -> Settings:
    return Settings(
        database_url=f"sqlite+pysqlite:///{tmp_path / 'test.db'}",
        local_parquet_dir=tmp_path / "parquet",
        tf_artifact_dir=tmp_path / "models",
        analytics_state_dir=tmp_path / "state",
        r2_endpoint_url="",
        r2_access_key_id="",
        r2_secret_access_key="",
        gcs_bucket="",
        bigquery_project_id="",
    )


@pytest.fixture()
def db_session(test_settings: Settings) -> Session:
    engine = create_engine(
        test_settings.database_url,
        future=True,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    session = factory()
    try:
        yield session
        session.commit()
    finally:
        session.close()
        engine.dispose()
