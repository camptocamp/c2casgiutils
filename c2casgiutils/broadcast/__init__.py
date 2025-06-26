"""Broadcast messages to all the processes of Gunicorn in every containers."""

import functools
import logging
import os
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from fastapi import FastAPI

import c2casgiutils.broadcast.redis
from c2casgiutils import redis_utils
from c2casgiutils.broadcast import interface, local

_LOG = logging.getLogger(__name__)
_BROADCAST_ENV_KEY = "C2C_BROADCAST_PREFIX"

_broadcaster: interface.BaseBroadcaster | None = None


async def setup_fastapi(app: FastAPI | None = None) -> None:
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

    global _broadcaster  # pylint: disable=global-statement
    broadcast_prefix = os.environ.get(_BROADCAST_ENV_KEY, "broadcast_api_")
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
    global _broadcaster  # pylint: disable=global-statement
    if _broadcaster is None:
        if need_init:
            _LOG.error("Broadcast functionality used before it is setup")
        _broadcaster = local.LocalBroadcaster()
    return _broadcaster


def cleanup() -> None:
    """Cleanup the broadcaster to force to reinitialize it."""
    global _broadcaster  # pylint: disable=global-statement
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


async def broadcast(
    channel: str,
    params: dict[str, Any] | None = None,
    expect_answers: bool = False,
    timeout: float = 10,
) -> list[Any] | None:
    """
    Broadcast a message to the given channel.

    If answers are expected, it will wait up to "timeout" seconds to get all the answers.
    """
    return await _get(need_init=True).broadcast(
        channel,
        params if params is not None else {},
        expect_answers,
        timeout,
    )


# We can also templatize the argument with Python 3.10
# See: https://www.python.org/dev/peps/pep-0612/
_DecoratorReturn = TypeVar("_DecoratorReturn")


async def decorate(
    func: Callable[..., Awaitable[_DecoratorReturn]],
    channel: str | None = None,
    expect_answers: bool = False,
    timeout: float = 10,
) -> Callable[..., Awaitable[list[_DecoratorReturn] | None]]:
    """
    Decorate function will be called through the broadcast functionality.

    If expect_answers is set to True, the returned value will be a list of all the answers.
    """

    @functools.wraps(func)
    async def wrapper(**kwargs: Any) -> list[_DecoratorReturn] | None:
        return await broadcast(_channel, params=kwargs, expect_answers=expect_answers, timeout=timeout)

    _channel = f"c2c_decorated_{func.__module__}.{func.__name__}" if channel is None else channel
    await subscribe(_channel, func)

    return wrapper
