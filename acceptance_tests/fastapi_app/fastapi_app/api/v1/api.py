import os

import sentry_sdk

# from c2casgiutils import tools
from fastapi import APIRouter

from fastapi_app.api.v1.endpoints import hello

if "SENTRY_URL" in os.environ:
    sentry_sdk.init(
        dsn=os.environ["SENTRY_URL"],
        # Add data like request headers and IP for users, if applicable;
        # see https://docs.sentry.io/platforms/python/data-management/data-collected/ for more info
        send_default_pii=True,
    )
api_router = APIRouter()
api_router.include_router(hello.router, prefix="/v1")
# api_router.include_router(tools.router, prefix="/c2c")
