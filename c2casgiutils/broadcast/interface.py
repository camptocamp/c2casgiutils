from abc import abstractmethod
from collections.abc import Awaitable, Callable, Mapping
from typing import Any


class BaseBroadcaster:
    """Interface definition for message broadcasting implementation."""

    async def init(self) -> None:
        """Initialize the broadcaster, if needed."""

    @abstractmethod
    async def subscribe(self, channel: str, callback: Callable[..., Awaitable[Any]]) -> None:
        """Subscribe to a channel."""

    @abstractmethod
    async def unsubscribe(self, channel: str) -> None:
        """Unsubscribe from a channel."""

    @abstractmethod
    async def broadcast(
        self,
        channel: str,
        params: Mapping[str, Any],
        expect_answers: bool,
        timeout: float,
    ) -> list[Any] | None:
        """Broadcast a message to a channel."""
