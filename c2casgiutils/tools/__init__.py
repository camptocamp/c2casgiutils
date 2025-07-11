import base64
import hashlib
import logging
from pathlib import Path
from typing import Annotated, cast

import aiofiles
from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.routing import Router

from c2casgiutils import auth, config
from c2casgiutils.tools import headers
from c2casgiutils.tools import logging_ as logging_tools

_LOGGER = logging.getLogger(__name__)

router = APIRouter()

router.include_router(
    headers.router,
    prefix="/headers",
    tags=["c2c_headers"],
    dependencies=[Depends(auth.require_admin_access)],
)
router.include_router(
    logging_tools.router,
    prefix="/logging",
    tags=["c2c_logging"],
    dependencies=[Depends(auth.require_admin_access)],
)


static_router = Router()
static_router.mount(
    "/static",
    StaticFiles(directory=Path(__file__).parent / "static"),
    name="c2c_static",
)


async def startup(main_app: FastAPI) -> None:
    """Initialize application on startup."""
    main_app.mount("/c2c_static", static_router)
    await logging_tools.startup(main_app)


_templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


async def _integrity(file_name: str) -> str:
    """Get the integrity of a file."""
    file_path = Path(__file__).parent / "static" / file_name
    if not file_path.exists():
        _LOGGER.error("File %s does not exist in static directory", file_name)
        return ""
    if not file_path.is_file():
        _LOGGER.error("Path %s is not a file in static directory", file_name)
        return ""
    async with aiofiles.open(file_path, mode="rb") as file:
        content = await file.read()
        hasher = hashlib.new("sha512", content)
        digest = hasher.digest()
        return f"sha512-{base64.standard_b64encode(digest).decode()}"


_FILES = ["favicon-16x16.png", "favicon-32x32.png", "index.js", "index.css"]


@router.get("/", response_class=HTMLResponse)
async def c2c_index(request: Request, auth_info: Annotated[auth.AuthInfo, Depends(auth.get_auth)]) -> str:
    """Get an interactive page to use the tools."""

    return cast(
        "str",
        _templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "is_auth": auth_info.is_logged_in,
                "has_access": await auth.check_admin_access(auth_info),
                "user": auth_info.user,
                "auth_type": auth.auth_type(),
                "AuthenticationType": auth.AuthenticationType,
                "application_module": config.settings.tools.logging.application_module,
                "integrity": {file_name: await _integrity(file_name) for file_name in _FILES},
            },
        ),
    )
