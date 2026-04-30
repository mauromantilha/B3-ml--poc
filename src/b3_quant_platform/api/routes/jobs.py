from __future__ import annotations

import base64
import hashlib
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from b3_quant_platform.api.dependencies import get_db_session
from b3_quant_platform.core.idempotency import build_idempotency_key, get_existing_job_run
from b3_quant_platform.ingestion.models import SourceFileDescriptor
from b3_quant_platform.ingestion.service import HistoricalB3IngestionService
from b3_quant_platform.models.entities import JobRun
from b3_quant_platform.models.enums import RunStatus
from b3_quant_platform.ml.tensorflow_baseline import TensorflowBaselineService
from b3_quant_platform.schemas.common import JobRunEnvelope
from b3_quant_platform.schemas.economic_models import EconomicModelsJobRequest
from b3_quant_platform.schemas.jobs import (
    AnalyticsMirrorRequest,
    EodReconcileRequest,
    HistoricalIngestionRequest,
    JobResult,
    TrainModelRequest,
)
from b3_quant_platform.services.analytics_mirror import AnalyticsMirrorService
from b3_quant_platform.services.economic_models_engine import EconomicModelsEngineService
from b3_quant_platform.services.eod_reconciliation import EodReconciliationService

router = APIRouter(tags=["jobs"])
eod_service = EodReconciliationService()
mirror_service = AnalyticsMirrorService()
training_service = TensorflowBaselineService()
historical_service = HistoricalB3IngestionService()
economic_models_service = EconomicModelsEngineService()


@router.post("/jobs/eod-reconcile", response_model=JobResult, status_code=status.HTTP_202_ACCEPTED)
def reconcile_eod(
    payload: EodReconcileRequest,
    session: Session = Depends(get_db_session),
) -> JobResult:
    job_run, details = eod_service.reconcile(session, payload)
    return JobResult(job_run=JobRunEnvelope.model_validate(job_run), details=details)


@router.post("/jobs/analytics-mirror", response_model=JobResult, status_code=status.HTTP_202_ACCEPTED)
def analytics_mirror(
    payload: AnalyticsMirrorRequest,
    session: Session = Depends(get_db_session),
) -> JobResult:
    reference_date = payload.reference_date or payload.processing_date
    job_run, reused = _get_or_create_job_run(
        session,
        "analytics_mirror",
        reference_date,
        payload.model_dump(mode="json"),
    )
    if reused:
        return JobResult(
            job_run=JobRunEnvelope.model_validate(job_run),
            details={"manifest_uri": job_run.result_uri, "bigquery_table": None, "reused": True},
        )

    result = mirror_service.mirror_rows(payload) if payload.rows else mirror_service.mirror_dataset(payload)
    job_run.status = RunStatus.SUCCEEDED
    job_run.result_uri = result.manifest_uri or result.gcs_uri
    session.flush()
    return JobResult(
        job_run=JobRunEnvelope.model_validate(job_run),
        details={
            "gcs_uri": result.gcs_uri,
            "bigquery_table": result.bigquery_table,
            "local_path": str(result.local_path),
            "manifest_uri": result.manifest_uri,
            "watermark_uri": result.watermark_uri,
            "external_table": result.external_table,
            "native_table": result.native_table,
            "mirrored_object_count": result.mirrored_object_count,
            "mirrored_uris": result.mirrored_uris,
            "ddl_statements": result.ddl_statements,
            "dml_statements": result.dml_statements,
            "reused": False,
        },
    )


@router.post("/jobs/historical-ingestion", response_model=JobResult, status_code=status.HTTP_202_ACCEPTED)
def historical_ingestion(
    payload: HistoricalIngestionRequest,
    session: Session = Depends(get_db_session),
) -> JobResult:
    job_reference_date = payload.reference_date or payload.processing_date
    job_payload = payload.model_dump(mode="json", exclude={"content_base64"})
    if payload.content_base64:
        job_payload["content_sha256"] = hashlib.sha256(payload.content_base64.encode("utf-8")).hexdigest()

    job_run, reused = _get_or_create_job_run(
        session,
        "historical_ingestion",
        job_reference_date,
        job_payload,
    )
    if reused:
        return JobResult(
            job_run=JobRunEnvelope.model_validate(job_run),
            details={"manifest_uri": job_run.result_uri, "reused": True},
        )

    if payload.content_base64:
        try:
            source_bytes = base64.b64decode(payload.content_base64, validate=True)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid content_base64") from exc

        descriptor = SourceFileDescriptor(
            path=Path(payload.source_name or "historical-file"),
            dataset_type=payload.dataset_type,
            processing_date=payload.processing_date,
            source_system=payload.source_system,
            reference_date=payload.reference_date,
            encoding=payload.encoding,
            delimiter=payload.delimiter,
        )
        result = historical_service.ingest_bytes(source_bytes, descriptor=descriptor)
    else:
        result = historical_service.ingest_file(
            file_path=Path(payload.file_path or ""),
            dataset_type=payload.dataset_type,
            processing_date=payload.processing_date,
            reference_date=payload.reference_date,
            source_system=payload.source_system,
            encoding=payload.encoding,
            delimiter=payload.delimiter,
        )

    job_run.status = RunStatus.SUCCEEDED
    job_run.result_uri = result.manifest.metadata_log_uri
    session.flush()
    return JobResult(
        job_run=JobRunEnvelope.model_validate(job_run),
        details={"manifest": result.manifest.to_dict(), "reused": False},
    )


@router.post("/jobs/train-model", response_model=JobResult, status_code=status.HTTP_202_ACCEPTED)
def train_model(
    payload: TrainModelRequest,
    session: Session = Depends(get_db_session),
) -> JobResult:
    job_run, reused = _get_or_create_job_run(
        session,
        "train_tensorflow_baseline",
        payload.reference_date,
        payload.model_dump(mode="json"),
    )
    if reused:
        return JobResult(
            job_run=JobRunEnvelope.model_validate(job_run),
            details={"artifact_uri": job_run.result_uri, "reused": True},
        )

    _, details = training_service.train(session, payload)
    job_run.status = RunStatus.SUCCEEDED
    job_run.result_uri = details["artifact_uri"]
    session.flush()
    return JobResult(job_run=JobRunEnvelope.model_validate(job_run), details={**details, "reused": False})


@router.post("/jobs/economic-models", response_model=JobResult, status_code=status.HTTP_202_ACCEPTED)
def economic_models(
    payload: EconomicModelsJobRequest,
    session: Session = Depends(get_db_session),
) -> JobResult:
    job_run, reused = _get_or_create_job_run(
        session,
        "economic_models_engine",
        payload.reference_date,
        payload.model_dump(mode="json"),
    )
    if reused:
        return JobResult(
            job_run=JobRunEnvelope.model_validate(job_run),
            details={"result_uri": job_run.result_uri, "reused": True},
        )

    result = economic_models_service.run(session, payload)
    job_run.status = RunStatus.SUCCEEDED
    job_run.result_uri = (
        f"feature-store-snapshot:{result.feature_store_snapshot_id}"
        if result.feature_store_snapshot_id is not None
        else f"economic-models:{payload.window.value}:{payload.reference_date.isoformat()}"
    )
    session.flush()
    return JobResult(
        job_run=JobRunEnvelope.model_validate(job_run),
        details={**result.model_dump(mode="json"), "reused": False},
    )


def _get_or_create_job_run(
    session: Session,
    job_name: str,
    reference_date,
    payload: dict[str, Any],
) -> tuple[JobRun, bool]:
    idempotency_key = build_idempotency_key(job_name, reference_date, payload)
    existing = get_existing_job_run(session, idempotency_key)
    if existing is not None and existing.status == RunStatus.SUCCEEDED:
        return existing, True

    job_run = existing or JobRun(
        job_name=job_name,
        reference_date=reference_date,
        idempotency_key=idempotency_key,
        status=RunStatus.RUNNING,
        payload_json=payload,
    )
    session.add(job_run)
    session.flush()
    return job_run, False
