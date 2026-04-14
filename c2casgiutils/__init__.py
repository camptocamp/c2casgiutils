import importlib.metadata
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from c2casgiutils import auth, broadcast, health_checks, tools

_LOGGER = logging.getLogger(__name__)

_BASE_DIR = Path(__file__).parent
_STATIC_DIR = _BASE_DIR / "static"

__version__ = importlib.metadata.version("c2casgiutils")


app = FastAPI(
    title="C2C ASGI Utils",
    description="Provide some tools for a Fast API application",
    version=__version__,
)

app.include_router(tools.router, prefix="", tags=["c2c_tools"])
app.include_router(health_checks.router, prefix="/health", tags=["c2c_health_checks"])
app.include_router(auth.router, prefix="/auth", tags=["c2c_auth"])
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="c2c_static")


async def startup(main_app: FastAPI) -> None:
    """Initialize application on startup."""
    await broadcast.startup(main_app)
    await tools.startup(main_app)
    await auth.startup(main_app)
