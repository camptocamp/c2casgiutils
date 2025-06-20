from collections.abc import Awaitable, Callable, Mapping, MutableMapping
from typing import Any

# noinspection PyProtectedMember
from c2casgiutils.broadcast import interface, utils


class LocalBroadcaster(interface.BaseBroadcaster):
    """Fake implementation of broadcasting messages (will just answer locally)."""

    def __init__(self) -> None:
        """Initialize the broadcaster."""
        self._subscribers: MutableMapping[str, Callable[..., Awaitable[Any]]] = {}

    async def subscribe(self, channel: str, callback: Callable[..., Awaitable[Any]]) -> None:
        """Subscribe to a channel. The callback must be a coroutine function."""
        self._subscribers[channel] = callback

    async def unsubscribe(self, channel: str) -> None:
        """Unsubscribe from a channel."""
        del self._subscribers[channel]

    async def broadcast(
        self,
        channel: str,
        params: Mapping[str, Any],
        expect_answers: bool,
        timeout: float,
    ) -> list[Any] | None:
        """Broadcast a message to all the listeners."""
        del timeout  # Not used
        subscriber = self._subscribers.get(channel, None)

        if subscriber is not None:
            response = await subscriber(**params)
            answers = [utils.add_host_info(response)]
        else:
            answers = []

        return answers if expect_answers else None

    def get_subscribers(self) -> Mapping[str, Callable[..., Awaitable[Any]]]:
        """Get the subscribers for testing purposes."""
        return self._subscribers
