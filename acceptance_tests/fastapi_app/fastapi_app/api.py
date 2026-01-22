import logging
from typing import Protocol

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

    result: list[str] | None = None


class _EchoHandlerInput(BaseModel):
    message: str


class _EchoHandlerOutput(BaseModel):
    message: str


class _EchoHandlerProto(Protocol):
    async def __call__(
        self, *, message: _EchoHandlerInput
    ) -> list[broadcast.BroadcastResponse[_EchoHandlerOutput]] | None: ...


_echo_handler: _EchoHandlerProto = None  # type: ignore[assignment]


@app.get("/broadcast")
async def send_broadcast() -> BroadcastResponse:
    """
    Send a broadcast message to a channel.
    """
    assert _echo_handler is not None, "Broadcast handler is not set up"
    return BroadcastResponse(
        result=[
            response.payload.message
            for response in await _echo_handler(message=_EchoHandlerInput(message="coucou"))
        ]
    )


# Create a handler that will receive broadcasts
async def __echo_handler(*, message: _EchoHandlerInput) -> _EchoHandlerOutput:
    """Echo handler for broadcast messages."""
    return _EchoHandlerOutput(message="Broadcast echo: " + message.message)


async def startup(main_app: FastAPI) -> None:
    """Initialize application on startup."""
    del main_app  # Unused parameter, but required
    global _echo_handler  # noqa: PLW0603
    _echo_handler = await broadcast.decorate(__echo_handler, expect_answers=True)
