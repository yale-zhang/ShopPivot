"""FastAPI 应用装配。

- 容器在 lifespan 启动时构建：加载模块 → 注册扩展点 → 装配适配器；
- 所有领域异常统一转 ErrorEnvelope（E001~E008 + err_layer）；
- 请求日志带 request_id / 耗时，不记录请求体（避免 PII 入日志）。
"""
from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest

from bootstrap.container import AppContainer, build_container
from bootstrap.routers.admin_router import router as admin_router
from bootstrap.routers.auth_router import router as auth_router
from bootstrap.routers.job_router import router as job_router
from bootstrap.routers.n8n_router import router as n8n_router
from bootstrap.routers.ops_router import router as ops_router
from bootstrap.routers.skill_router import router as skill_router
from bootstrap.routers.sourcing_router import router as sourcing_router
from bootstrap.routers.workbench_router import router as workbench_router
from bootstrap.routers.write_router import router as write_router
from bootstrap.settings import Settings, get_settings
from shared.errors.registry import DomainError
from shared.logging.json_logger import configure_logging, get_logger

log = get_logger("shoppivot.api")
REQUESTS = Counter(
    "shoppivot_http_requests_total", "HTTP requests", ["method", "path", "status"]
)


def _error_response(
    code: str, layer: str, message: str, user_message: str, retryable: bool, status: int,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={
            "code": code,
            "layer": layer,
            "message": message,
            "user_message": user_message,
            "retryable": retryable,
            "details": details or {},
        },
    )


def create_app(
    settings: Settings | None = None,
    *,
    container: AppContainer | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if app.state.container is None:
            log.info("container building", extra={"env": settings.env})
            app.state.container = build_container(settings)
            report = app.state.container.startup_report
            log.info(
                "modules assembled",
                extra={
                    "loaded": report.loaded if report else [],
                    "blocked": len(report.blocked) if report else 0,
                    "contributions": report.contribution_count if report else 0,
                },
            )
        yield

    app = FastAPI(
        title="店枢 ShopPivot API",
        version="0.1.0",
        description="RPA 电商自动化运营平台 M0（只读 S01）",
        lifespan=lifespan,
    )
    app.state.container = container
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_log(request: Request, call_next):  # type: ignore[no-untyped-def]
        request_id = request.headers.get("x-request-id") or f"req_{uuid.uuid4().hex[:12]}"
        started = time.perf_counter()
        response = await call_next(request)
        cost_ms = int((time.perf_counter() - started) * 1000)
        REQUESTS.labels(request.method, request.url.path, str(response.status_code)).inc()
        response.headers["X-Request-Id"] = request_id
        log.info(
            "http request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "cost_ms": cost_ms,
            },
        )
        return response

    @app.exception_handler(DomainError)
    async def domain_error_handler(_request: Request, exc: DomainError) -> JSONResponse:
        return _error_response(
            exc.code,
            str(exc.layer),
            exc.message,
            exc.user_message,
            exc.retryable,
            exc.http_status,
            exc.details,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return _error_response(
            "E006",
            "CODE",
            "请求参数校验失败",
            "请求参数不合法，请检查后重试",
            False,
            422,
            {"errors": exc.errors()},
        )

    @app.get("/metrics", include_in_schema=False)
    def metrics() -> PlainTextResponse:
        return PlainTextResponse(generate_latest().decode(), media_type=CONTENT_TYPE_LATEST)

    app.include_router(auth_router)
    app.include_router(job_router)
    app.include_router(workbench_router)
    app.include_router(ops_router)
    app.include_router(admin_router)
    app.include_router(n8n_router)
    app.include_router(write_router)
    app.include_router(sourcing_router)
    app.include_router(skill_router)
    return app


app = create_app()
