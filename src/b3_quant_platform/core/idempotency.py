from __future__ import annotations

import hashlib
from datetime import date
from typing import Any

import orjson
from sqlalchemy import select
from sqlalchemy.orm import Session


def build_idempotency_key(job_name: str, reference_date: date, payload: dict[str, Any]) -> str:
    payload_bytes = orjson.dumps(payload, option=orjson.OPT_SORT_KEYS)
    digest = hashlib.sha256(f"{job_name}:{reference_date.isoformat()}:".encode() + payload_bytes).hexdigest()
    return digest


def get_existing_job_run(session: Session, idempotency_key: str):
    from b3_quant_platform.models.entities import JobRun

    statement = select(JobRun).where(JobRun.idempotency_key == idempotency_key)
    return session.scalar(statement)
