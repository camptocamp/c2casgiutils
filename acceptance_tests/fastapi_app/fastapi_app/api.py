import logging
from collections.abc import Awaitable, Callable
from typing import Any

from c2casgiutils import broadcast
from fastapi import FastAPI
from pydantic import BaseModel

_LOG = logging.getLogger(__name__)

app = FastAPI(title="fastapi_app API")


class HelloResponse(BaseModel):
    """Response of the hello endpoint."""

    message: str = ""


@app.get("/hello")
async def hello() -> HelloResponse:
    """
    Get a hello message.
    """
    return HelloResponse(message="hello")


class BroadcastResponse(BaseModel):
    """Response from broadcast endpoint."""

    result: list[dict[str, Any]] | None = None


_echo_handler: Callable[[], Awaitable[list[dict[str, Any]] | None]] = None  # type: ignore[assignment]


@app.get("/broadcast")
async def send_broadcast() -> BroadcastResponse:
    """
    Send a broadcast message to a channel.
    """
    assert _echo_handler is not None, "Broadcast handler is not set up"
    return BroadcastResponse(result=await _echo_handler())


# Create a handler that will receive broadcasts
async def __echo_handler() -> dict[str, Any]:
    """Echo handler for broadcast messages."""
    return {"message": "Broadcast echo"}


async def startup(main_app: FastAPI) -> None:
    """Initialize application on startup."""
    del main_app  # Unused parameter, but required
    global _echo_handler  # pylint: disable=global-statement
    _echo_handler = await broadcast.decorate(__echo_handler, expect_answers=True)
