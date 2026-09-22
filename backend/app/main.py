"""FastAPI application entry point."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.actions.registry import ConfigError
from app.api.routes import api_keys, auth, dashboard, hooks, system, workflows
from app.core.config import settings
from app.core.net import UnsafeTargetError
from app.db.session import init_db

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)-8s %(name)s: %(message)s"
)
logger = logging.getLogger("app")

DESCRIPTION = """
Turn an incoming webhook into an action somewhere else.

* `POST /hooks/{token}` accepts a JSON payload and answers `202` with an
  execution id; the action runs in the background with up to three attempts.
* Actions are adapters — Discord, Telegram and a generic HTTP request — each
  with its own validated configuration.
* Management routes accept either the dashboard's session cookie or an
  `X-API-Key` header.
"""


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_db()
    logger.info(
        "Webhook Automation Hub ready (environment=%s, max_attempts=%s)",
        settings.environment,
        settings.max_attempts,
    )
    yield


app = FastAPI(
    title="Webhook Automation Hub",
    description=DESCRIPTION,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key", "X-Hub-Signature-256"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):  # noqa: ANN001, ANN201
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Cache-Control", "no-store")
    return response


@app.exception_handler(ConfigError)
async def config_error_handler(_: Request, exc: ConfigError) -> JSONResponse:
    return JSONResponse({"detail": str(exc)}, status_code=422)


@app.exception_handler(UnsafeTargetError)
async def unsafe_target_handler(_: Request, exc: UnsafeTargetError) -> JSONResponse:
    return JSONResponse({"detail": str(exc)}, status_code=422)


app.include_router(system.router)
app.include_router(auth.router)
app.include_router(workflows.router)
app.include_router(api_keys.router)
app.include_router(dashboard.router)
app.include_router(hooks.router)


@app.get("/", include_in_schema=False)
def index() -> JSONResponse:
    return JSONResponse(
        {
            "service": "webhook-automation-hub",
            "docs": "/docs",
            "health": "/api/health",
        }
    )
