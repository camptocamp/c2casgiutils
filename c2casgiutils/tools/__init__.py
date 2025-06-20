import logging
from pathlib import Path
from typing import cast

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.routing import Router

from c2casgiutils import auth

_LOGGER = logging.getLogger(__name__)

router = APIRouter()

static_router = Router()
static_router.mount(
    "/static",
    StaticFiles(directory=Path(__file__).parent / "static"),
    name="c2c_static",
)

_templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


@router.get("/", response_class=HTMLResponse)
async def c2c_index(request: Request) -> str:
    """Return the index.html tool file."""
    is_auth, user = await auth.is_auth_user(request)

    return cast(
        "str",
        _templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "is_auth": is_auth,
                "user": user,
                "auth_type": auth.auth_type(),
                "AuthenticationType": auth.AuthenticationType,
            },
        ),
    )
