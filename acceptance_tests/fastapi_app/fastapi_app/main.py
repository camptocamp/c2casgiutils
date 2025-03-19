from app.api.v1.api import api_router as api_router_v1
from app.core.config import settings
from fastapi import FastAPI
from pydantic.generics import GenericModel
from starlette.middleware.cors import CORSMiddleware

# Core Application Instance
app = FastAPI(
    title="fastapi_app",
    version=settings.API_VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
)

# Set all CORS origins enabled
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


class RootResponse(GenericModel):
    """Response of the root endpoint."""

    message: str = ""


@app.get("/")
async def root() -> RootResponse:
    """
    Return a hello message.
    """
    return {"message": "Hello World"}


# Add Routers
app.include_router(api_router_v1, prefix=settings.API_V1_STR)
