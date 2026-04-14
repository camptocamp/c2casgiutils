import asyncio
import base64
import hashlib
import logging
from typing import Annotated, cast

from anyio import Path
from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from c2casgiutils import auth, config
from c2casgiutils.tools import headers
from c2casgiutils.tools import logging_ as logging_tools

_LOGGER = logging.getLogger(__name__)

_BASE_DIR = Path(__file__).parent
_TEMPLATES_DIR = _BASE_DIR / "templates"
_STATIC_DIR = _BASE_DIR.parent / "static"

_templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

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


async def startup(main_app: FastAPI) -> None:
    """Initialize application on startup."""
    await logging_tools.startup(main_app)


async def _integrity(file_name: str) -> str:
    """Get the integrity of a file."""
    file_path = _STATIC_DIR / file_name
    if not await file_path.exists():
        _LOGGER.error("File %s does not exist in static directory", file_name)
        return ""
    if not await file_path.is_file():
        _LOGGER.error("Path %s is not a file in static directory", file_name)
        return ""
    content = await file_path.read_bytes()
    hasher = hashlib.new("sha512", content)
    digest = hasher.digest()
    return f"sha512-{base64.standard_b64encode(digest).decode()}"


_FILES = ["favicon-16x16.png", "favicon-32x32.png", "index.js", "index.css"]


@router.get("/", response_class=HTMLResponse)
async def c2c_index(request: Request, auth_info: Annotated[auth.AuthInfo, Depends(auth.get_auth)]) -> str:
    """Get an interactive page to use the tools."""
    integrity_entries = await asyncio.gather(*(_integrity(file_name) for file_name in _FILES))
    integrity = dict(zip(_FILES, integrity_entries, strict=True))
    return cast(
        "str",
        _templates.TemplateResponse(
            request,
            "index.html",
            {
                "request": request,
                "is_auth": auth_info.is_logged_in,
                "has_access": await auth.check_admin_access(auth_info),
                "user": auth_info.user,
                "auth_type": auth.auth_type(),
                "AuthenticationType": auth.AuthenticationType,
                "application_module": config.settings.tools.logging.application_module,
                "integrity": integrity,
            },
        ),
    )
