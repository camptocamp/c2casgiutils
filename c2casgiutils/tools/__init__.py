import logging
from pathlib import Path
from typing import cast

from fastapi import APIRouter, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.routing import Router

from c2casgiutils import auth, config, health_checks
from c2casgiutils.tools import headers
from c2casgiutils.tools import logging_ as logging_tools

_LOGGER = logging.getLogger(__name__)

router = APIRouter()

router.include_router(auth.router, prefix="/auth", tags=["c2c_auth"])
router.include_router(headers.router, prefix="/headers", tags=["c2c_headers"])
router.include_router(logging_tools.router, prefix="/logging", tags=["c2c_logging"])
router.include_router(health_checks.router, prefix="/health", tags=["c2c_lhealth_checks"])

static_router = Router()
static_router.mount(
    "/static",
    StaticFiles(directory=Path(__file__).parent / "static"),
    name="c2c_static",
)

_templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


@router.get("/", response_class=HTMLResponse)
async def c2c_index(request: Request, response: Response) -> str:
    """Return the index.html tool file."""
    is_auth, user = await auth.is_auth_user(request)

    return cast(
        "str",
        _templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "is_auth": is_auth,
                "has_access": await auth.check_access(request, response),
                "user": user,
                "auth_type": auth.auth_type(),
                "AuthenticationType": auth.AuthenticationType,
                "application_module": config.settings.tools.logging.application_module,
            },
        ),
    )
