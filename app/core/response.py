"""
Every response this API sends — success or error — follows this envelope,
because the frontend (already built, not modifiable) reads responses this
way (see src/services/actions/auth.action.js):

    { "success": bool, "message": str, "data": {...} | None,
      "verification_required": bool, "errors": {...} | None }

FastAPI's default behaviors (HTTPException -> {"detail": "..."},
RequestValidationError -> {"detail": [...]}) do NOT match this shape, so
both are intercepted by exception handlers below and re-wrapped. Router
handlers in app/api/v1/*.py should use success_response()/the
AppError exception (not raw HTTPException) so every path produces the
correct envelope.
"""

from math import ceil
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


def success_response(
    *,
    message: str = "OK",
    data: Any = None,
    verification_required: bool = False,
    status_code: int = status.HTTP_200_OK,
) -> JSONResponse:
    body = {
        "success": True,
        "message": message,
        "data": data,
        "verification_required": verification_required,
        "errors": None,
    }
    return JSONResponse(status_code=status_code, content=jsonable_encoder(body))


def paginated_data(
    *,
    items: list[Any],
    total: int,
    page: int = 1,
    limit: int = 10,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Formats list + pagination metadata in the exact structure the frontend
    expects across SchoolsPage, UsersPage, TeachersPage, StudentsPage,
    ClassroomOperatorsPage, and Academics pages."""
    safe_page = max(1, page)
    safe_limit = max(1, limit)
    total_pages = ceil(total / safe_limit) if total > 0 else 1
    return {
        "list": items,
        "pagination": {
            "page": safe_page,
            "limit": safe_limit,
            "size": safe_limit,
            "total": total,
            "total_count": total,
            "total_page": total_pages,
            "totalPages": total_pages,
            "has_more": (safe_page * safe_limit) < total,
            "extra": extra or {},
        },
    }


class AppError(Exception):
    """Raise this from service/router code for any expected error condition
    (bad credentials, invalid OTP, user not found, etc.) instead of
    FastAPI's HTTPException, so the response body matches the envelope
    shape the frontend expects. `errors` is optional structured detail
    (e.g. field-level validation issues); most call sites just pass a
    message and leave errors as None."""

    def __init__(self, message: str, *, status_code: int = 400, errors: dict | None = None):
        self.message = message
        self.status_code = status_code
        self.errors = errors
        super().__init__(message)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        body = {
            "success": False,
            "message": exc.message,
            "data": None,
            "verification_required": False,
            "errors": exc.errors,
        }
        return JSONResponse(status_code=exc.status_code, content=jsonable_encoder(body))

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        body = {
            "success": False,
            "message": str(exc.detail) if exc.detail else "Request failed.",
            "data": None,
            "verification_required": False,
            "errors": None,
        }
        return JSONResponse(status_code=exc.status_code, content=jsonable_encoder(body))

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Re-shape Pydantic's validation error list into the envelope's
        # `errors` field instead of FastAPI's default {"detail": [...]}.
        field_errors = {}
        for err in exc.errors():
            loc = ".".join(str(part) for part in err["loc"] if part != "body")
            field_errors[loc or "body"] = err["msg"]

        body = {
            "success": False,
            "message": "Invalid request data.",
            "data": None,
            "verification_required": False,
            "errors": field_errors,
        }
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=jsonable_encoder(body)
        )

    from sqlalchemy.exc import IntegrityError

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(
        request: Request, exc: IntegrityError
    ) -> JSONResponse:
        body = {
            "success": False,
            "message": "Invalid reference ID or duplicate record conflict.",
            "data": None,
            "verification_required": False,
            "errors": None,
        }
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST, content=jsonable_encoder(body)
        )


    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        # Last-resort catch-all — never leak a raw traceback/stack message
        # to the client. Logging a real system would use proper structured
        # logging here; kept to a print for this phase's scope.
        print(f"[UNHANDLED ERROR] {request.method} {request.url.path}: {exc!r}")
        body = {
            "success": False,
            "message": "An unexpected error occurred. Please try again.",
            "data": None,
            "verification_required": False,
            "errors": None,
        }
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=jsonable_encoder(body)
        )

