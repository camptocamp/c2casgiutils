import logging

from fastapi import FastAPI
from pydantic import BaseModel

_LOG = logging.getLogger(__name__)

app = FastAPI(title="{{cookiecutter.project_slug}} API")


class TodoResponse(BaseModel):
    """Response of the todo endpoint."""

    message: str = ""


@app.get("/todo")
async def todo() -> TodoResponse:
    """
    Get a todo message.
    """
    return TodoResponse(message="todo: implement me!")


async def startup(main_app: FastAPI) -> None:
    """Initialize application on startup."""
    # Unused parameter, but required to be consistent with the signature of the other startup functions.
    del main_app
