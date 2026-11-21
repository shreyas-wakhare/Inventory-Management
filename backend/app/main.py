"""FastAPI application entrypoint and factory."""

import uuid

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_v1_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.shared.schemas import HealthResponse
from database.session import check_db_connection


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    configure_logging(debug=settings.APP_DEBUG)

    application = FastAPI(
        title=settings.APP_NAME,
        version="1.0.0",
        debug=settings.APP_DEBUG,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.middleware("http")
    async def attach_trace_id(request: Request, call_next) -> Response:
        trace_id = request.headers.get("X-Trace-Id") or f"req_{uuid.uuid4().hex[:12]}"
        request.state.trace_id = trace_id
        response = await call_next(request)
        response.headers["X-Trace-Id"] = trace_id
        return response

    register_exception_handlers(application)

    @application.get("/health", response_model=HealthResponse, tags=["health"])
    def health_check() -> HealthResponse:
        db_status = "connected" if check_db_connection() else "disconnected"
        return HealthResponse(
            status="ok" if db_status == "connected" else "degraded",
            service=settings.APP_NAME,
            environment=settings.APP_ENV,
            database=db_status,
        )

    application.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)
    return application


app = create_app()
