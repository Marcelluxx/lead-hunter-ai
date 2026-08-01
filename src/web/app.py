from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from ..infrastructure.redis import RateLimitExceeded
from .dependencies import WebRuntime
from .routes import auth, jobs, usage, workspaces


def create_app(runtime: WebRuntime) -> FastAPI:
    app = FastAPI(title="Lead Hunter API", version="0.1.0")
    app.state.runtime = runtime

    @app.exception_handler(RateLimitExceeded)
    def rate_limit_handler(_: Request, exc: RateLimitExceeded):
        return JSONResponse(status_code=429, content={"detail": str(exc)})

    @app.get("/health/live", include_in_schema=False)
    def live():
        return {"status": "ok"}

    app.include_router(auth.router)
    app.include_router(jobs.router)
    app.include_router(usage.router)
    app.include_router(workspaces.router)
    return app
