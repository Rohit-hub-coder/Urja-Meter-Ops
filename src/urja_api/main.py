import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.staticfiles import StaticFiles

from src.urja_api.api.routes import consumption, health, hierarchy, meters, sync
from src.urja_api.errors import (
    AppException,
    ProblemDetails,
    app_exception_handler,
    generic_exception_handler,
)
from src.urja_api.storage.database import init_database


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure SQLite database schema and indexes exist
    await init_database()

    # Auto-seed cache on cold start if database is empty and credentials are configured
    from src.urja_api.api.dependencies import get_repository, get_sync_service
    from src.urja_api.config import settings

    repo = get_repository()
    count = await repo.get_total_meters_count()
    if count == 0 and settings.portal_username and settings.portal_password:
        try:
            sync_service = get_sync_service()
            await sync_service.sync_all(force=True)
        except Exception:
            # If upstream is unreachable during startup, let service start so /health and offline fallback can operate
            pass

    yield
    # Shutdown


app = FastAPI(
    title="Urja Meter Ops API Service",
    description=(
        "Production-grade RESTful API service providing clean, documented, and resilient access "
        "to the legacy Urja Meter Ops smart-metering portal."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# RFC 7807 Exception Handlers
app.add_exception_handler(AppException, app_exception_handler)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    problem = ProblemDetails(
        type="https://api.urja-ops.local/errors/validation-error",
        title="Invalid Request Parameters",
        status=422,
        detail="One or more request parameters failed validation.",
        instance=request.url.path,
        code="VALIDATION_ERROR",
        invalid_params=exc.errors(),
    )
    return JSONResponse(
        status_code=422, content=problem.model_dump(exclude_none=True), media_type="application/problem+json"
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    code_map = {
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        400: "BAD_REQUEST",
    }
    code = code_map.get(exc.status_code, f"HTTP_{exc.status_code}")
    title_map = {
        404: "Resource Not Found",
        405: "Method Not Allowed",
        400: "Bad Request",
    }
    title = title_map.get(exc.status_code, exc.detail if isinstance(exc.detail, str) else "HTTP Error")
    detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    problem = ProblemDetails(
        type=f"https://api.urja-ops.local/errors/{code.lower().replace('_', '-')}",
        title=title,
        status=exc.status_code,
        detail=detail,
        instance=request.url.path,
        code=code,
    )
    headers = getattr(exc, "headers", None)
    return JSONResponse(
        status_code=exc.status_code,
        content=problem.model_dump(exclude_none=True),
        media_type="application/problem+json",
        headers=headers,
    )


app.add_exception_handler(Exception, generic_exception_handler)

DEFAULT_ERROR_RESPONSES = {
    400: {"model": ProblemDetails, "description": "Bad Request"},
    404: {"model": ProblemDetails, "description": "Resource Not Found"},
    422: {"model": ProblemDetails, "description": "Validation Error"},
    502: {"model": ProblemDetails, "description": "Upstream Gateway Error"},
    503: {"model": ProblemDetails, "description": "Service Unavailable"},
}

# Include API Routers
app.include_router(meters.router, responses=DEFAULT_ERROR_RESPONSES)
app.include_router(consumption.router, responses=DEFAULT_ERROR_RESPONSES)
app.include_router(hierarchy.router, responses=DEFAULT_ERROR_RESPONSES)
app.include_router(sync.router, responses=DEFAULT_ERROR_RESPONSES)
app.include_router(health.router, responses=DEFAULT_ERROR_RESPONSES)

# Serve Web Console / Dashboard
STATIC_DIR = os.path.join(os.path.dirname(__file__), "web", "static")
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.api_route("/ui", methods=["GET", "HEAD"], include_in_schema=False)
    @app.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
    async def serve_ui():
        return FileResponse(os.path.join(STATIC_DIR, "index.html"))
