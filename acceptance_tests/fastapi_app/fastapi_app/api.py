import logging
from collections.abc import Awaitable, Callable
from typing import Any

from c2casgiutils import broadcast
from fastapi import APIRouter
from pydantic import BaseModel

_LOG = logging.getLogger(__name__)

router = APIRouter()


class HelloResponse(BaseModel):
    """Response of the hello endpoint."""

    message: str = ""


@router.get("/hello")
async def hello() -> HelloResponse:
    """
    Get a hello message.
    """
    return HelloResponse(message="hello")


class BroadcastResponse(BaseModel):
    """Response from broadcast endpoint."""

    result: list[dict[str, Any]] | None = None


echo_handler: Callable[[], Awaitable[list[dict[str, Any]] | None]] = None  # type: ignore[assignment]


@router.get("/broadcast")
async def send_broadcast() -> BroadcastResponse:
    """
    Send a broadcast message to a channel.
    """
    return BroadcastResponse(result=await echo_handler())


# Create a handler that will receive broadcasts
async def echo_handler_() -> dict[str, Any]:
    """Echo handler for broadcast messages."""
    return {"message": "Broadcast echo"}


# Subscribe the handler to a channel on module import
@router.on_event("startup")
async def setup_broadcast_handlers() -> None:
    """Setups broadcast handlers when the API starts."""
    global echo_handler  # pylint: disable=global-statement
    echo_handler = await broadcast.decorate(echo_handler_, expect_answers=True)
