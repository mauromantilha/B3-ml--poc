from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

import click

from b3_quant_platform.core.db import get_engine, get_session_factory
from b3_quant_platform.ingestion.models import HistoricalDatasetType
from b3_quant_platform.ingestion.service import HistoricalB3IngestionService
from b3_quant_platform.schemas.economic_models import EconomicModelsJobRequest
from b3_quant_platform.schemas.eod import MarketSnapshotBatchCreate
from b3_quant_platform.schemas.jobs import AnalyticsMirrorRequest, EodReconcileRequest, TrainModelRequest
from b3_quant_platform.services.analytics_mirror import AnalyticsMirrorService
from b3_quant_platform.services.economic_models_engine import EconomicModelsEngineService
from b3_quant_platform.services.eod_reconciliation import EodReconciliationService
from b3_quant_platform.services.market_data import MarketDataService
from b3_quant_platform.services.portfolio_factory import PortfolioFactoryService

portfolio_service = PortfolioFactoryService()
market_service = MarketDataService()
eod_service = EodReconciliationService()
mirror_service = AnalyticsMirrorService()
economic_models_service = EconomicModelsEngineService()


@click.group()
def cli() -> None:
    """Operational jobs for the B3 multi-portfolio platform."""


@contextmanager
def session_scope() -> Iterator[Any]:
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@cli.command("seed-templates")
def seed_templates() -> None:
    with session_scope() as session:
        created, skipped, templates = portfolio_service.seed_default_templates(session)
        click.echo(json.dumps({"created": created, "skipped": skipped, "templates": templates}, indent=2))


@cli.command("apply-migrations")
@click.option(
    "--dir",
    "migrations_dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path("sql/migrations"),
    show_default=True,
)
def apply_migrations(migrations_dir: Path) -> None:
    engine = get_engine()
    applied_files: list[str] = []
    raw_connection = engine.raw_connection()
    cursor = raw_connection.cursor()
    try:
        for migration_file in sorted(migrations_dir.glob("*.sql")):
            cursor.execute(migration_file.read_text())
            applied_files.append(migration_file.name)
        raw_connection.commit()
    except Exception:
        raw_connection.rollback()
        raise
    finally:
        cursor.close()
        raw_connection.close()

    click.echo(json.dumps({"applied": applied_files, "migration_dir": str(migrations_dir)}, indent=2))


@cli.command("ingest-historical")
@click.option("--file", "file_path", type=click.Path(exists=True, dir_okay=False, path_type=Path), required=True)
@click.option(
    "--dataset-type",
    type=click.Choice([item.value for item in HistoricalDatasetType]),
    required=True,
)
@click.option("--processing-date", type=click.DateTime(formats=["%Y-%m-%d"]))
@click.option("--reference-date", type=click.DateTime(formats=["%Y-%m-%d"]))
@click.option("--source-system", default="b3", show_default=True)
@click.option("--encoding", default="latin-1", show_default=True)
@click.option("--delimiter", default=None)
def ingest_historical(
    file_path: Path,
    dataset_type: str,
    processing_date: Any,
    reference_date: Any,
    source_system: str,
    encoding: str,
    delimiter: str | None,
) -> None:
    service = HistoricalB3IngestionService()
    result = service.ingest_file(
        file_path=file_path,
        dataset_type=dataset_type,
        processing_date=processing_date.date() if processing_date else None,
        reference_date=reference_date.date() if reference_date else None,
        source_system=source_system,
        encoding=encoding,
        delimiter=delimiter,
    )
    click.echo(json.dumps(result.manifest.to_dict(), indent=2))


@cli.command("ingest-snapshots")
@click.option("--file", "file_path", type=click.Path(exists=True, path_type=Path), required=True)
def ingest_snapshots(file_path: Path) -> None:
    payload = MarketSnapshotBatchCreate.model_validate_json(file_path.read_text())
    with session_scope() as session:
        snapshots, artifacts = market_service.ingest_snapshots(session, payload)
        click.echo(
            json.dumps(
                {
                    "snapshot_count": len(snapshots),
                    "artifacts": artifacts,
                },
                indent=2,
            )
        )


@cli.command("reconcile-eod")
@click.option("--file", "file_path", type=click.Path(exists=True, path_type=Path), required=True)
def reconcile_eod(file_path: Path) -> None:
    payload = EodReconcileRequest.model_validate_json(file_path.read_text())
    with session_scope() as session:
        job_run, details = eod_service.reconcile(session, payload)
        click.echo(json.dumps({"job_run_id": str(job_run.id), "details": details}, indent=2))


@cli.command("analytics-mirror")
@click.option("--file", "file_path", type=click.Path(exists=True, path_type=Path), required=True)
def analytics_mirror(file_path: Path) -> None:
    payload = AnalyticsMirrorRequest.model_validate_json(file_path.read_text())
    result = mirror_service.mirror_rows(payload) if payload.rows else mirror_service.mirror_dataset(payload)
    click.echo(
        json.dumps(
            {
                "gcs_uri": result.gcs_uri,
                "local_path": str(result.local_path),
                "bigquery_table": result.bigquery_table,
                "manifest_uri": result.manifest_uri,
                "watermark_uri": result.watermark_uri,
                "external_table": result.external_table,
                "native_table": result.native_table,
                "mirrored_object_count": result.mirrored_object_count,
                "mirrored_uris": result.mirrored_uris,
                "ddl_statements": result.ddl_statements,
                "dml_statements": result.dml_statements,
            },
            indent=2,
        )
    )


@cli.command("train-model")
@click.option("--file", "file_path", type=click.Path(exists=True, path_type=Path), required=True)
def train_model(file_path: Path) -> None:
    from b3_quant_platform.ml.tensorflow_baseline import TensorflowBaselineService

    payload = TrainModelRequest.model_validate_json(file_path.read_text())
    with session_scope() as session:
        _, details = TensorflowBaselineService().train(session, payload)
        click.echo(json.dumps(details, indent=2))


@cli.command("economic-models")
@click.option("--file", "file_path", type=click.Path(exists=True, path_type=Path), required=True)
def economic_models(file_path: Path) -> None:
    payload = EconomicModelsJobRequest.model_validate_json(file_path.read_text())
    with session_scope() as session:
        result = economic_models_service.run(session, payload)
        click.echo(json.dumps(result.model_dump(mode="json"), indent=2))
