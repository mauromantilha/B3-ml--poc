from __future__ import annotations

import time
from uuid import uuid4

import structlog
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from b3_quant_platform.api.routes.eod import router as eod_router
from b3_quant_platform.api.routes.events import router as events_router
from b3_quant_platform.api.routes.health import router as health_router
from b3_quant_platform.api.routes.jobs import router as jobs_router
from b3_quant_platform.api.routes.portfolios import router as portfolios_router
from b3_quant_platform.api.routes.scenarios import router as scenarios_router
from b3_quant_platform.core.config import get_settings
from b3_quant_platform.core.logging import configure_logging, get_logger

logger = get_logger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings)

    app = FastAPI(title=settings.app_name, version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        request_id = request.headers.get("x-request-id", str(uuid4()))
        structlog.contextvars.bind_contextvars(request_id=request_id)
        started_at = time.perf_counter()
        logger.info("request_started", method=request.method, path=request.url.path)
        try:
            response = await call_next(request)
        finally:
            elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
            logger.info("request_completed", method=request.method, path=request.url.path, elapsed_ms=elapsed_ms)
            structlog.contextvars.clear_contextvars()
        response.headers["x-request-id"] = request_id
        return response

    app.include_router(health_router)
    app.include_router(portfolios_router, prefix=settings.api_prefix)
    app.include_router(events_router, prefix=settings.api_prefix)
    app.include_router(scenarios_router, prefix=settings.api_prefix)
    app.include_router(eod_router, prefix=settings.api_prefix)
    app.include_router(jobs_router, prefix=settings.api_prefix)
    return app


app = create_app()


def run() -> None:
    settings = get_settings()
    uvicorn.run(
        "b3_quant_platform.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.environment == "local",
    )
