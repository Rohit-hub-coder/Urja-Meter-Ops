from typing import Optional

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


class ProblemDetails(BaseModel):
    """RFC 7807 Problem Details representation."""

    type: str = Field(
        default="about:blank",
        description="A URI reference that identifies the problem type.",
        json_schema_extra={"example": "https://api.urja-ops.local/errors/not-found"},
    )
    title: str = Field(
        ...,
        description="A short, human-readable summary of the problem type.",
        json_schema_extra={"example": "Resource Not Found"},
    )
    status: int = Field(
        ...,
        description="The HTTP status code.",
        json_schema_extra={"example": 404},
    )
    detail: Optional[str] = Field(
        None,
        description="A human-readable explanation specific to this occurrence.",
        json_schema_extra={"example": "Meter 'J999999' was not found."},
    )
    instance: Optional[str] = Field(
        None,
        description="A URI reference that identifies the specific occurrence.",
        json_schema_extra={"example": "/api/v1/meters/J999999"},
    )
    code: Optional[str] = Field(
        None,
        description="Machine-readable application error code.",
        json_schema_extra={"example": "NOT_FOUND"},
    )
    invalid_params: Optional[list] = Field(
        None,
        description="Details for validation errors if applicable.",
    )


class AppException(Exception):
    def __init__(
        self,
        status_code: int,
        title: str,
        detail: Optional[str] = None,
        code: Optional[str] = None,
        invalid_params: Optional[list] = None,
    ):
        super().__init__(detail or title)
        self.status_code = status_code
        self.title = title
        self.detail = detail
        self.code = code or self.__class__.__name__
        self.invalid_params = invalid_params


class NotFoundError(AppException):
    def __init__(self, resource: str, identifier: str):
        super().__init__(
            status_code=404,
            title="Resource Not Found",
            detail=f"{resource} '{identifier}' was not found.",
            code="NOT_FOUND",
        )


class UpstreamPortalError(AppException):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(
            status_code=status_code, title="Upstream Portal Error", detail=message, code="UPSTREAM_PORTAL_ERROR"
        )


class UpstreamTimeoutError(AppException):
    def __init__(self, message: str = "The upstream portal timed out answering the request."):
        super().__init__(status_code=504, title="Upstream Gateway Timeout", detail=message, code="UPSTREAM_TIMEOUT")


class UpstreamUnavailableError(AppException):
    def __init__(self, message: str = "The upstream portal is currently unreachable or unavailable."):
        super().__init__(
            status_code=503, title="Upstream Service Unavailable", detail=message, code="UPSTREAM_UNAVAILABLE"
        )


class RateLimitExceededError(AppException):
    def __init__(
        self,
        message: str = "Rate limit exceeded. Please wait before retrying.",
        retry_after: Optional[int] = None,
    ):
        super().__init__(status_code=429, title="Too Many Requests", detail=message, code="RATE_LIMIT_EXCEEDED")
        self.retry_after = retry_after


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    problem = ProblemDetails(
        type=f"https://api.urja-ops.local/errors/{exc.code.lower().replace('_', '-')}",
        title=exc.title,
        status=exc.status_code,
        detail=exc.detail,
        instance=request.url.path,
        code=exc.code,
        invalid_params=exc.invalid_params,
    )
    headers = {}
    if hasattr(exc, "retry_after") and exc.retry_after is not None:
        headers["Retry-After"] = str(exc.retry_after)
    return JSONResponse(
        status_code=exc.status_code,
        content=problem.model_dump(exclude_none=True),
        media_type="application/problem+json",
        headers=headers or None,
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Never leak stack traces or internal details to the consumer
    problem = ProblemDetails(
        type="https://api.urja-ops.local/errors/internal-server-error",
        title="Internal Server Error",
        status=500,
        detail="An unexpected internal error occurred while processing the request.",
        instance=request.url.path,
        code="INTERNAL_SERVER_ERROR",
    )
    return JSONResponse(
        status_code=500, content=problem.model_dump(exclude_none=True), media_type="application/problem+json"
    )
