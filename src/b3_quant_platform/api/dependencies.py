from __future__ import annotations

from collections.abc import Generator

from sqlalchemy.orm import Session

from b3_quant_platform.core.db import get_session


def get_db_session() -> Generator[Session, None, None]:
    yield from get_session()
