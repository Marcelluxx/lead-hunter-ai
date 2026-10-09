from __future__ import annotations
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import request_validation_exception_handler

from ..infrastructure.redis import RateLimitExceeded
from .dependencies import WebRuntime
from .routes import auth, jobs, privacy, usage, workspaces, feature_licenses


def create_app(runtime: WebRuntime) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_):
        try:
            yield
        finally:
            runtime.database.close_license_clock_pool()

    app = FastAPI(title="Lead Hunter API", version="0.1.0", lifespan=lifespan)
    app.state.runtime = runtime
    if runtime.license_settings is not None:
        runtime.license_settings.validate_server()

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        if "/feature-licenses/" in request.url.path:
            return JSONResponse(status_code=422, content={"detail": "license_invalid"})
        return await request_validation_exception_handler(request, exc)

    @app.exception_handler(RateLimitExceeded)
    def rate_limit_handler(_: Request, exc: RateLimitExceeded):
        return JSONResponse(status_code=429, content={"detail": str(exc)})

    @app.get("/health/live", include_in_schema=False)
    def live():
        return {"status": "ok"}

    app.include_router(auth.router)
    app.include_router(jobs.router)
    app.include_router(privacy.router)
    app.include_router(usage.router)
    app.include_router(workspaces.router)
    app.include_router(feature_licenses.router)
    return app
