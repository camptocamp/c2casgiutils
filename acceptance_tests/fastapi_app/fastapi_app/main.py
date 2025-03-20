import logging
import os

import sentry_sdk
from c2casgiutils import tools
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from fastapi_app.api import router as api_router

_LOGGER = logging.getLogger(__name__)

if "SENTRY_URL" in os.environ:
    sentry_sdk.init(
        dsn=os.environ["SENTRY_URL"],
        # Add data like request headers and IP for users, if applicable;
        # see https://docs.sentry.io/platforms/python/data-management/data-collected/ for more info
        send_default_pii=True,
    )

# Core Application Instance
app = FastAPI(
    title="fastapi_app",
    openapi_url="/api/openapi.json",
)

# Set all CORS origins enabled
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RootResponse(BaseModel):
    """Response of the root endpoint."""

    message: str


@app.get("/")
async def root() -> RootResponse:
    """
    Return a hello message.
    """
    return RootResponse(message="Hello World")


# Add Routers
app.include_router(api_router, prefix="/api")
app.include_router(tools.router, prefix="/c2c")
app.mount("/c2c_static", tools.static_router)
