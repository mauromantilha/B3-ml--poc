from __future__ import annotations

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from b3_quant_platform.core.config import Settings, get_settings
from b3_quant_platform.core.logging import get_logger
from b3_quant_platform.models.base import Base

logger = get_logger(__name__)


def _engine_connect_args(database_url: str) -> dict[str, object]:
    if database_url.startswith("sqlite"):
        return {"check_same_thread": False}
    if "pooler.supabase.com" in database_url or ":6543/" in database_url:
        return {"prepare_threshold": None}
    return {}


@lru_cache(maxsize=1)
def get_engine(settings: Settings | None = None) -> Engine:
    app_settings = settings or get_settings()
    engine_kwargs: dict[str, object] = {
        "future": True,
        "pool_pre_ping": True,
        "connect_args": _engine_connect_args(app_settings.database_url),
    }
    if not app_settings.database_url.startswith("sqlite"):
        engine_kwargs.update({"pool_recycle": 300, "pool_size": 5, "max_overflow": 5})

    engine = create_engine(
        app_settings.database_url,
        **engine_kwargs,
    )
    if app_settings.database_url.startswith("sqlite"):
        Base.metadata.create_all(engine)
        logger.info("sqlite_schema_ready", database_url=app_settings.database_url)
    return engine


@lru_cache(maxsize=1)
def get_session_factory(settings: Settings | None = None) -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(settings), autoflush=False, autocommit=False, expire_on_commit=False)


def get_session() -> Generator[Session, None, None]:
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
