import logging
from typing import Protocol, TypedDict

from c2casgiutils import broadcast
from c2casgiutils.broadcast import MissingAnswer
from c2casgiutils.broadcast import types as broadcast_types
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


class AppBroadcastResponses(BaseModel):
    """Response from broadcast endpoint."""

    dict_: list[str]
    async_dict: list[str]
    pydantic: list[str]
    async_pydantic: list[str]


class _EchoHandlerInputDict(TypedDict):
    message: str


class _EchoHandlerOutputDict(TypedDict):
    message: str


class _EchoHandlerProtoDict(Protocol):
    async def __call__(
        self, *, message: _EchoHandlerInputDict
    ) -> list[broadcast_types.BroadcastResponse[_EchoHandlerOutputDict] | MissingAnswer]: ...


_echo_handler_dict: _EchoHandlerProtoDict = None  # type: ignore[assignment]
_echo_handler_async_dict: _EchoHandlerProtoDict = None  # type: ignore[assignment]


class _EchoHandlerInputPydantic(BaseModel):
    message: str


class _EchoHandlerOutputPydantic(BaseModel):
    message: str


class _EchoHandlerProtoPydantic(Protocol):
    async def __call__(
        self, *, message: _EchoHandlerInputPydantic
    ) -> list[broadcast_types.BroadcastResponse[_EchoHandlerOutputPydantic] | MissingAnswer]: ...


_echo_handler_pydantic: _EchoHandlerProtoPydantic = None  # type: ignore[assignment]
_echo_handler_async_pydantic: _EchoHandlerProtoPydantic = None  # type: ignore[assignment]


@app.get("/broadcast")
async def send_broadcast() -> AppBroadcastResponses:
    """
    Send a broadcast message to a channel.
    """
    assert _echo_handler_dict is not None, "Broadcast handler is not set up"
    assert _echo_handler_async_dict is not None, "Broadcast handler is not set up"
    assert _echo_handler_pydantic is not None, "Broadcast handler is not set up"
    assert _echo_handler_async_pydantic is not None, "Broadcast handler is not set up"

    responses_dict = []
    responses_async_dict = []
    responses_pydantic = []
    responses_async_pydantic = []

    error = None
    try:
        responses_dict = await _echo_handler_dict(message=_EchoHandlerInputDict(message="coucou"))
    except Exception as e:  # noqa: BLE001
        _LOG.error("Failed sending broadcast message to dict handler", exc_info=True)
        error = e

    try:
        responses_async_dict = await _echo_handler_async_dict(message=_EchoHandlerInputDict(message="coucou"))
    except Exception as e:  # noqa: BLE001
        _LOG.error("Failed sending broadcast message to async dict handler", exc_info=True)
        error = e

    try:
        responses_pydantic = await _echo_handler_pydantic(message=_EchoHandlerInputPydantic(message="coucou"))
    except Exception as e:  # noqa: BLE001
        _LOG.error("Failed sending broadcast message to pydantic handler", exc_info=True)
        error = e

    try:
        responses_async_pydantic = await _echo_handler_async_pydantic(
            message=_EchoHandlerInputPydantic(message="coucou")
        )
    except Exception as e:  # noqa: BLE001
        _LOG.error("Failed sending broadcast message to async pydantic handler", exc_info=True)
        error = e

    if error is not None:
        raise error

    errors = [
        *[error for error in responses_dict if isinstance(error, MissingAnswer)],
        *[error for error in responses_async_dict if isinstance(error, MissingAnswer)],
        *[error for error in responses_pydantic if isinstance(error, MissingAnswer)],
        *[error for error in responses_async_pydantic if isinstance(error, MissingAnswer)],
    ]
    if any(errors):
        _LOG.warning(
            "Some broadcast messages did not receive an answer.",
        )

    return AppBroadcastResponses(
        dict_=[
            response.payload["message"]
            for response in responses_dict
            if not isinstance(response, MissingAnswer)
        ],
        async_dict=[
            response.payload["message"]
            for response in responses_async_dict
            if not isinstance(response, MissingAnswer)
        ],
        pydantic=[
            response.payload.message
            for response in responses_pydantic
            if not isinstance(response, MissingAnswer)
        ],
        async_pydantic=[
            response.payload.message
            for response in responses_async_pydantic
            if not isinstance(response, MissingAnswer)
        ],
    )


# Create a handler that will receive broadcasts
def __echo_handler_dict(*, message: _EchoHandlerInputDict) -> _EchoHandlerOutputDict:
    """Echo handler for broadcast messages."""
    return _EchoHandlerOutputDict(message="Broadcast echo dict: " + message["message"])


async def __echo_handler_async_dict(*, message: _EchoHandlerInputDict) -> _EchoHandlerOutputDict:
    """Echo handler for broadcast messages."""
    return _EchoHandlerOutputDict(message="Broadcast echo async dict: " + message["message"])


def __echo_handler_pydantic(*, message: _EchoHandlerInputPydantic) -> _EchoHandlerOutputPydantic:
    """Echo handler for broadcast messages."""
    return _EchoHandlerOutputPydantic(message="Broadcast echo pydantic: " + message.message)


async def __echo_handler_async_pydantic(*, message: _EchoHandlerInputPydantic) -> _EchoHandlerOutputPydantic:
    """Echo handler for broadcast messages."""
    return _EchoHandlerOutputPydantic(message="Broadcast echo async pydantic: " + message.message)


async def startup(main_app: FastAPI) -> None:
    """Initialize application on startup."""
    del main_app  # Unused parameter, but required
    global _echo_handler_dict, _echo_handler_async_dict, _echo_handler_pydantic, _echo_handler_async_pydantic  # noqa: PLW0603
    _echo_handler_dict = await broadcast.decorate(__echo_handler_dict, expect_answers=True)
    _echo_handler_async_dict = await broadcast.decorate(__echo_handler_async_dict, expect_answers=True)
    _echo_handler_pydantic = await broadcast.decorate(__echo_handler_pydantic, expect_answers=True)
    _echo_handler_async_pydantic = await broadcast.decorate(
        __echo_handler_async_pydantic, expect_answers=True
    )
