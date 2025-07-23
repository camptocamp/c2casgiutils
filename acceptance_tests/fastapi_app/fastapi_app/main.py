import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import c2casgiutils
import sentry_sdk
from c2casgiutils import config, headers, health_checks
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from prometheus_client import start_http_server
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel

from fastapi_app import api

_LOGGER = logging.getLogger(__name__)

# Initialize Sentry if the URL is provided
if config.settings.sentry.dsn or "SENTRY_DSN" in os.environ:
    _LOGGER.info("Sentry is enabled with URL: %s", config.settings.sentry.dsn or os.environ.get("SENTRY_DSN"))
    sentry_sdk.init(**config.settings.sentry.model_dump())


@asynccontextmanager
async def _lifespan(main_app: FastAPI) -> AsyncGenerator[None, None]:
    """Handle application lifespan events."""

    _LOGGER.info("Starting the application")
    await c2casgiutils.startup(main_app)
    await api.startup(main_app)

    yield


# Core Application Instance
app = FastAPI(title="fastapi_app API", lifespan=_lifespan)


# Add TrustedHostMiddleware (should be first)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"],  # Configure with specific hosts in production
)

http = os.environ.get("HTTP", "False").lower() in ["true", "1"]
# Add HTTPSRedirectMiddleware
if not http:
    app.add_middleware(HTTPSRedirectMiddleware)

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
    headers_config={
        "http": {"headers": {"Strict-Transport-Security": None} if http else {}},
    },
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


# Add Routers
app.mount("/api", api.app)
app.mount("/c2c", c2casgiutils.app)

# Get Prometheus HTTP server port from environment variable 9000 by default
start_http_server(config.settings.prometheus.port)

instrumentator = Instrumentator(should_instrument_requests_inprogress=True)
instrumentator.instrument(app)
