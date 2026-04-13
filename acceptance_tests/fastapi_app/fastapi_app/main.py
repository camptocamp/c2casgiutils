import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import c2casgiutils
import sentry_sdk
from c2casgiutils import config, headers, health_checks
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import RedirectResponse
from prometheus_client import start_http_server
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel

from fastapi_app import api

_LOGGER = logging.getLogger(__name__)

# Initialize Sentry if the URL is provided
if config.settings.sentry.dsn or "SENTRY_DSN" in os.environ:
    _LOGGER.info("Sentry is enabled with URL: %s", config.settings.sentry.dsn or os.environ.get("SENTRY_DSN"))
    sentry_sdk.init(
        **{k: v for k, v in config.settings.sentry.model_dump().items() if v is not None and k != "tags"}
    )

    for tag, value in config.settings.sentry.tags.items():
        sentry_sdk.set_tag(tag, value)


@asynccontextmanager
async def _lifespan(main_app: FastAPI) -> AsyncGenerator[None, None]:
    """Handle application lifespan events."""

    _LOGGER.info("Starting the application")
    await c2casgiutils.startup(main_app)
    await api.startup(main_app)

    if config.settings.prometheus.port > 0:
        # Get Prometheus HTTP server port from environment variable 9000 by default
        start_http_server(config.settings.prometheus.port)

    yield


# Core Application Instance
app = FastAPI(title="fastapi_app API", lifespan=_lifespan)


# Add TrustedHostMiddleware (should be first)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"],  # Configure with specific hosts in production
)

# Add GZipMiddleware
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Set all CORS origins enabled
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    headers.ArmorHeaderMiddleware,
    headers_config={"http": {"headers": {"Strict-Transport-Security": None}}} if config.settings.http else {},
)


class RootResponse(BaseModel):
    """Response of the root endpoint."""

    message: str


# Add Health Checks
health_checks.FACTORY.add(health_checks.Redis(tags=["liveness", "redis", "all"]))
health_checks.FACTORY.add(health_checks.Wrong(tags=["wrong", "all"]))


@app.get("/")
async def root() -> RootResponse:
    """
    Return a hello message.
    """
    return RootResponse(message="Hello World")


@app.get("/c2c")
async def redirect_c2c(request: Request) -> RedirectResponse:
    """Redirect to the mounted `c2c` app canonical path."""
    url = request.url
    redirect_url = url.path + "/"
    if url.query:
        redirect_url += f"?{url.query}"
    return RedirectResponse(url=redirect_url, status_code=307)


# Add Routers
app.mount("/api", api.app)
app.mount("/c2c", c2casgiutils.app)

instrumentator = Instrumentator(should_instrument_requests_inprogress=True)
instrumentator.instrument(app)
