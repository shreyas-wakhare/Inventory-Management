"""Structured domain exception hierarchy and global FastAPI exception handlers (SDD-2 Section 5.6)."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, ProgrammingError

logger = logging.getLogger("ser.exceptions")


class AppException(Exception):
    """Base application exception producing the standard SDD-2 error envelope."""

    def __init__(
        self,
        message: str,
        *,
        error_code: str = "APPLICATION_ERROR",
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}


class UnauthorizedError(AppException):
    def __init__(
        self,
        message: str = "Authentication required.",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            error_code="UNAUTHORIZED",
            status_code=status.HTTP_401_UNAUTHORIZED,
            details=details,
        )


class InsufficientRoleError(AppException):
    def __init__(
        self,
        message: str = "You do not have permission to perform this action.",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            error_code="INSUFFICIENT_ROLE",
            status_code=status.HTTP_403_FORBIDDEN,
            details=details,
        )


class NotFoundError(AppException):
    def __init__(
        self,
        message: str = "Requested resource was not found.",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            error_code="RESOURCE_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            details=details,
        )


class DuplicateBusinessKeyError(AppException):
    def __init__(
        self,
        message: str = "A resource with this unique identifier already exists.",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            error_code="DUPLICATE_BUSINESS_KEY",
            status_code=status.HTTP_409_CONFLICT,
            details=details,
        )


class UnitLockedInReplenishmentError(AppException):
    def __init__(
        self,
        message: str = "Equipment unit is locked in workshop REPLENISHMENT and cannot be dispatched.",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            error_code="UNIT_LOCKED_IN_REPLENISHMENT",
            status_code=status.HTTP_409_CONFLICT,
            details=details,
        )


class UnitNotAvailableError(AppException):
    def __init__(
        self,
        message: str = "Equipment unit is not available for this operation.",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            error_code="UNIT_NOT_AVAILABLE",
            status_code=status.HTTP_409_CONFLICT,
            details=details,
        )


class UnitNotAtProjectError(AppException):
    def __init__(
        self,
        message: str = "Equipment unit is not currently deployed at this project.",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            error_code="UNIT_NOT_AT_PROJECT",
            status_code=status.HTTP_409_CONFLICT,
            details=details,
        )


class ProjectHasActiveEquipmentError(AppException):
    def __init__(
        self,
        message: str = "Project cannot be closed while equipment or reconciliations remain active.",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            error_code="PROJECT_HAS_ACTIVE_EQUIPMENT",
            status_code=status.HTTP_409_CONFLICT,
            details=details,
        )


class InsufficientStockError(AppException):
    def __init__(
        self,
        message: str = "Insufficient stock balance to complete this operation.",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            error_code="INSUFFICIENT_STOCK",
            status_code=status.HTTP_409_CONFLICT,
            details=details,
        )


class InvalidStateTransitionError(AppException):
    def __init__(
        self,
        message: str = "Operation is not permitted in the current resource state.",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            error_code="INVALID_STATE_TRANSITION",
            status_code=status.HTTP_409_CONFLICT,
            details=details,
        )


class ReconciliationBoundsError(AppException):
    def __init__(
        self,
        message: str = "Returned and lost quantities cannot exceed dispatched quantity.",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            error_code="RECONCILIATION_BOUNDS_EXCEEDED",
            status_code=status.HTTP_409_CONFLICT,
            details=details,
        )


class ProjectNotActiveError(AppException):
    def __init__(
        self,
        message: str = "Target project must be ACTIVE for this operation.",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            error_code="PROJECT_NOT_ACTIVE",
            status_code=status.HTTP_409_CONFLICT,
            details=details,
        )


class ValidationDomainError(AppException):
    def __init__(
        self,
        message: str = "Request violates domain validation rules.",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            error_code="DOMAIN_VALIDATION_ERROR",
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            details=details,
        )


class LedgerImmutabilityError(AppException):
    def __init__(
        self,
        message: str = "stock_movements is an immutable append-only ledger.",
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            error_code="LEDGER_IMMUTABLE",
            status_code=status.HTTP_409_CONFLICT,
            details=details,
        )


def _get_trace_id(request: Request) -> str:
    return getattr(request.state, "trace_id", f"req_{uuid.uuid4().hex[:12]}")


def _error_payload(
    *,
    error_code: str,
    message: str,
    details: dict[str, Any] | list[Any] | None,
    trace_id: str,
) -> dict[str, Any]:
    return {
        "error": {
            "error_code": error_code,
            "message": message,
            "details": details if details is not None else {},
            "trace_id": trace_id,
        }
    }


def register_exception_handlers(app: FastAPI) -> None:
    """Attach global SDD-2 error handlers to the FastAPI application."""

    @app.exception_handler(AppException)
    async def handle_app_exception(request: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_payload(
                error_code=exc.error_code,
                message=exc.message,
                details=exc.details,
                trace_id=_get_trace_id(request),
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=_error_payload(
                error_code="VALIDATION_ERROR",
                message="Request validation failed.",
                details={"errors": exc.errors()},
                trace_id=_get_trace_id(request),
            ),
        )

    @app.exception_handler(HTTPException)
    async def handle_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_payload(
                error_code=f"HTTP_{exc.status_code}",
                message=str(exc.detail),
                details={},
                trace_id=_get_trace_id(request),
            ),
        )

    @app.exception_handler(IntegrityError)
    async def handle_integrity_error(request: Request, exc: IntegrityError) -> JSONResponse:
        trace_id = _get_trace_id(request)
        logger.warning("Database integrity conflict [%s]: %s", trace_id, exc.orig)
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=_error_payload(
                error_code="DATABASE_CONFLICT",
                message="Operation violated a database uniqueness or integrity constraint.",
                details={},
                trace_id=trace_id,
            ),
        )

    @app.exception_handler(ProgrammingError)
    async def handle_programming_error(request: Request, exc: ProgrammingError) -> JSONResponse:
        trace_id = _get_trace_id(request)
        logger.error("Database execution error [%s]: %s", trace_id, exc.orig)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_payload(
                error_code="INTERNAL_SERVER_ERROR",
                message="An internal database error occurred.",
                details={},
                trace_id=trace_id,
            ),
        )

    @app.exception_handler(Exception)
    async def handle_unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
        trace_id = _get_trace_id(request)
        logger.exception("Unhandled server exception [%s]", trace_id, exc_info=exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_payload(
                error_code="INTERNAL_SERVER_ERROR",
                message="An unexpected internal error occurred.",
                details={},
                trace_id=trace_id,
            ),
        )
