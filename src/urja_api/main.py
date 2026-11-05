import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

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


app.add_exception_handler(Exception, generic_exception_handler)

# Include API Routers
app.include_router(meters.router)
app.include_router(consumption.router)
app.include_router(hierarchy.router)
app.include_router(sync.router)
app.include_router(health.router)

# Serve Web Console / Dashboard
STATIC_DIR = os.path.join(os.path.dirname(__file__), "web", "static")
if os.path.exists(STATIC_DIR):

    @app.api_route("/ui", methods=["GET", "HEAD"], include_in_schema=False)
    @app.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
    async def serve_ui():
        return FileResponse(os.path.join(STATIC_DIR, "index.html"))
