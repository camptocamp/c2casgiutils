import logging
from pathlib import Path
from typing import cast

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.routing import Router

_LOGGER = logging.getLogger(__name__)

router = APIRouter()

static_router = Router()
static_router.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="c2c_static")

_templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


@router.get("/", response_class=HTMLResponse)
async def c2c_tools(request: Request) -> str:
    """Return the index.html tool file."""
    return cast(
        "str",
        _templates.TemplateResponse(
            "index.html",
            {
                "request": request,
            },
        ),
    )
