"""Broadcast messages to all the processes of Gunicorn in every containers."""

import asyncio
import logging
from collections.abc import Awaitable, Callable, Coroutine
from typing import Any, Literal, ParamSpec, TypeVar, cast, get_type_hints, overload

from fastapi import FastAPI
from pydantic import BaseModel

import c2casgiutils.broadcast.redis
from c2casgiutils import config, redis_utils
from c2casgiutils.broadcast import interface, local
from c2casgiutils.broadcast.types import BroadcastResponse

_LOG = logging.getLogger(__name__)

_broadcaster: interface.BaseBroadcaster | None = None


async def startup(app: FastAPI | None = None) -> None:
    """
    Initialize the broadcaster with Redis, if configured. (FastAPI integration).

    Otherwise, fall back to a fake local implementation.

    To be used in FastAPI startup event handler:

    ```python
    @app.on_event("startup")
    async def startup_event():
        await c2casgiutils.broadcast.setup_fastapi(app)
    ```
    """
    del app  # Not used, but kept for compatibility with FastAPI

    global _broadcaster  # noqa: PLW0603
    broadcast_prefix = config.settings.redis.broadcast_prefix
    master, slave, _ = redis_utils.get()
    if _broadcaster is None:
        if master is not None and slave is not None:
            _broadcaster = c2casgiutils.broadcast.redis.RedisBroadcaster(broadcast_prefix, master, slave)
            _LOG.info("Broadcast service setup using Redis implementation")
        else:
            _broadcaster = local.LocalBroadcaster()
            _LOG.info("Broadcast service setup using local implementation")
        await _broadcaster.init()
    elif isinstance(_broadcaster, local.LocalBroadcaster) and master is not None and slave is not None:
        _LOG.info("Switching from a local broadcaster to a Redis broadcaster")
        prev_broadcaster = _broadcaster
        _broadcaster = c2casgiutils.broadcast.redis.RedisBroadcaster(broadcast_prefix, master, slave)
        await _broadcaster.init()
        await _broadcaster.copy_local_subscriptions(prev_broadcaster)


def _get(need_init: bool = False) -> interface.BaseBroadcaster:
    global _broadcaster  # noqa: PLW0603
    if _broadcaster is None:
        if need_init:
            _LOG.error("Broadcast functionality used before it is setup")
        _broadcaster = local.LocalBroadcaster()
    return _broadcaster


def cleanup() -> None:
    """Cleanup the broadcaster to force to reinitialize it."""
    global _broadcaster  # noqa: PLW0603
    _broadcaster = None


async def subscribe(channel: str, callback: Callable[..., Awaitable[Any]]) -> None:
    """
    Subscribe to a broadcast channel with the given callback.

    The callback will be called with its parameters
    taken from the dict provided in the _broadcaster.broadcast "params" parameter.
    The callback must be a coroutine function (async def).

    A channel can be subscribed only once.
    """
    await _get().subscribe(channel, callback)


async def unsubscribe(channel: str) -> None:
    """Unsubscribe from a channel."""
    await _get().unsubscribe(channel)


class MissingAnswer:
    """Result placeholder for a missing answer when expect_answers is True, can happened with Redis."""


async def broadcast(
    channel: str,
    params: dict[str, Any] | None = None,
    expect_answers: bool = False,
    timeout: float = 10,
) -> list[BroadcastResponse[Any] | MissingAnswer] | None:
    """
    Broadcast a message to the given channel.

    If answers are expected, it will wait up to "timeout" seconds to get all the answers.
    """
    responses = await _get(need_init=True).broadcast(
        channel, params if params is not None else {}, expect_answers, timeout
    )
    if responses is None:
        return None

    return [
        BroadcastResponse(**response) if response is not None else MissingAnswer() for response in responses
    ]


_DecoratorArgs = ParamSpec("_DecoratorArgs")
_DecoratorReturn = TypeVar("_DecoratorReturn")


def _serialize_params(params: dict[str, Any]) -> dict[str, Any]:
    """Serialize params, converting Pydantic models to dicts."""
    result = {}
    for key, value in params.items():
        if isinstance(value, BaseModel):
            result[key] = value.model_dump(mode="json")
        else:
            result[key] = value
    return result


def _deserialize_payload(payload: Any, return_type: Any) -> Any:
    """Deserialize payload if return_type is a Pydantic model."""
    if return_type is None or not isinstance(return_type, type):
        return payload

    if isinstance(payload, dict) and issubclass(return_type, BaseModel):
        return return_type.model_validate(payload)

    return payload


def _deserialize_kwargs(kwargs: dict[str, Any], func: Callable[..., Any]) -> dict[str, Any]:
    """Deserialize kwargs if their types are Pydantic models."""
    hints = get_type_hints(func)

    result: dict[str, Any] = {}
    for key, value in kwargs.items():
        if key in hints:
            param_type = hints[key]
            if isinstance(value, dict) and isinstance(param_type, type) and issubclass(param_type, BaseModel):
                result[key] = param_type.model_validate(value)
            else:
                result[key] = value
        else:
            result[key] = value

    return result


def _get_return_type(func: Callable[..., Any]) -> Any:
    """Extract the return type from a function, handling Awaitable types."""
    # Get the return type from the decorated function
    hints = get_type_hints(func)
    return hints.get("return")


# For expect_answers=True
@overload
async def decorate(
    func: Callable[_DecoratorArgs, Awaitable[_DecoratorReturn] | _DecoratorReturn],
    channel: str | None = None,
    *,
    expect_answers: Literal[True],
    timeout: float = 10,
) -> Callable[
    _DecoratorArgs, Coroutine[Any, Any, list[BroadcastResponse[_DecoratorReturn] | MissingAnswer]]
]: ...


# For expect_answers=False
@overload
async def decorate(
    func: Callable[_DecoratorArgs, Awaitable[_DecoratorReturn] | _DecoratorReturn],
    channel: str | None = None,
    *,
    expect_answers: Literal[False] = False,
    timeout: float = 10,
) -> Callable[_DecoratorArgs, Coroutine[Any, Any, None]]: ...


# For no expect_answers parameter (defaults to False behavior)
@overload
async def decorate(
    func: Callable[_DecoratorArgs, Awaitable[_DecoratorReturn] | _DecoratorReturn],
    channel: str | None = None,
    *,
    timeout: float = 10,
) -> Callable[_DecoratorArgs, Coroutine[Any, Any, None]]: ...


async def decorate(
    func: Callable[_DecoratorArgs, Awaitable[_DecoratorReturn] | _DecoratorReturn],
    channel: str | None = None,
    expect_answers: bool = False,
    timeout: float = 10,
) -> Callable[
    _DecoratorArgs, Coroutine[Any, Any, list[BroadcastResponse[_DecoratorReturn] | MissingAnswer] | None]
]:
    """
    Decorate function will be called through the broadcast functionality.

    If expect_answers is set to True, the returned value will be a list of all the answers.
    """

    _channel = f"c2c_decorated_{func.__module__}.{func.__name__}" if channel is None else channel

    async def wrapper(
        *args: _DecoratorArgs.args,
        **kwargs: _DecoratorArgs.kwargs,
    ) -> list[BroadcastResponse[_DecoratorReturn] | MissingAnswer] | None:
        """Wrap the function to call the decorated function."""
        assert not args, "Broadcast decorator should not be called with positional arguments"
        # Serialize Pydantic models in kwargs
        serialized_kwargs = _serialize_params(kwargs)
        if expect_answers:
            responses = await broadcast(
                _channel, params=serialized_kwargs, expect_answers=True, timeout=timeout
            )
            if responses is None:
                return None

            return_type = _get_return_type(func)

            # Deserialize payloads in responses
            for response in responses:
                if isinstance(response, BroadcastResponse):
                    response.payload = _deserialize_payload(response.payload, return_type)
            return cast("list[BroadcastResponse[_DecoratorReturn] | MissingAnswer]", responses)
        await broadcast(_channel, params=serialized_kwargs, expect_answers=False, timeout=timeout)
        return None

    async def async_wrapper(
        *args: _DecoratorArgs.args,
        **kwargs: _DecoratorArgs.kwargs,
    ) -> _DecoratorReturn:
        """Wrap the function to await it if it is a coroutine."""
        assert not args, "Broadcast decorator should not be called with positional arguments"
        result = func(*args, **kwargs)
        if asyncio.iscoroutine(result):
            return cast("_DecoratorReturn", await result)
        return cast("_DecoratorReturn", result)

    async def subscribe_func(
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        # Deserialize kwargs if they should contain Pydantic models
        deserialized_kwargs = _deserialize_kwargs(kwargs, func)
        result = await async_wrapper(*args, **deserialized_kwargs)
        if isinstance(result, BaseModel):
            return result.model_dump(mode="json")
        return result

    await subscribe(_channel, subscribe_func)

    return wrapper
