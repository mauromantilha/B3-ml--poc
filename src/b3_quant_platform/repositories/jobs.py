from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import select

from b3_quant_platform.models.entities import AuditLog, JobExecution, SystemJob
from b3_quant_platform.models.enums import JobTarget, RunStatus
from b3_quant_platform.repositories.base import SQLAlchemyRepository


class SystemJobRepository(SQLAlchemyRepository[SystemJob]):
    model = SystemJob

    def upsert_system_job(
        self,
        *,
        job_name: str,
        service_name: JobTarget,
        schedule_cron: str | None,
        idempotency_scope: str = "reference_date",
        config_json: dict[str, Any] | None = None,
    ) -> SystemJob:
        job = self.session.scalar(select(SystemJob).where(SystemJob.job_name == job_name))
        if job is None:
            job = SystemJob(
                job_name=job_name,
                service_name=service_name,
                schedule_cron=schedule_cron,
                idempotency_scope=idempotency_scope,
                active=True,
                config_json=config_json or {},
            )
            return self.add(job)

        job.service_name = service_name
        job.schedule_cron = schedule_cron
        job.idempotency_scope = idempotency_scope
        job.config_json = config_json or {}
        self.session.flush()
        return job


class JobExecutionRepository(SQLAlchemyRepository[JobExecution]):
    model = JobExecution

    def begin_execution(
        self,
        *,
        job_name: str,
        reference_date: date,
        idempotency_key: str,
        status: RunStatus,
        payload_json: dict[str, Any] | None = None,
        system_job_id: UUID | None = None,
    ) -> JobExecution:
        execution = self.session.scalar(
            select(JobExecution).where(JobExecution.idempotency_key == idempotency_key)
        )
        if execution is None:
            execution = JobExecution(
                system_job_id=system_job_id,
                job_name=job_name,
                reference_date=reference_date,
                idempotency_key=idempotency_key,
                status=status,
                payload_json=payload_json or {},
                error_json={},
            )
            return self.add(execution)

        execution.system_job_id = system_job_id
        execution.status = status
        execution.payload_json = payload_json or {}
        self.session.flush()
        return execution

    def complete_execution(
        self,
        execution: JobExecution,
        *,
        status: RunStatus,
        result_uri: str | None = None,
        error_json: dict[str, Any] | None = None,
    ) -> JobExecution:
        execution.status = status
        execution.result_uri = result_uri
        execution.error_json = error_json or {}
        self.session.flush()
        return execution


class AuditLogRepository(SQLAlchemyRepository[AuditLog]):
    model = AuditLog

    def append_log(
        self,
        *,
        entity_type: str,
        action: str,
        entity_id: UUID | None = None,
        actor_user_id: UUID | None = None,
        request_id: str | None = None,
        trace_id: str | None = None,
        before_json: dict[str, Any] | None = None,
        after_json: dict[str, Any] | None = None,
        metadata_json: dict[str, Any] | None = None,
    ) -> AuditLog:
        entry = AuditLog(
            actor_user_id=actor_user_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            request_id=request_id,
            trace_id=trace_id,
            before_json=before_json or {},
            after_json=after_json or {},
            metadata_json=metadata_json or {},
        )
        return self.add(entry)
