import asyncio
import json
import logging
import random
import string
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

import redis.exceptions

from c2casgiutils.broadcast import interface, local, utils

_LOG = logging.getLogger(__name__)


class AsyncPubSubWorker:
    """
    A native async implementation of the Redis PubSub worker that doesn't die when connections are broken.
    """

    def __init__(self, pubsub: "redis.asyncio.client.PubSub", name: str | None = None) -> None:
        """Initialize the AsyncPubSubWorker."""
        self.pubsub = pubsub
        self.running = False
        self._task: asyncio.Task[None] | None = None
        self.name = name

    async def start(self) -> None:
        """Start the worker as a background task."""
        if self._task is None:
            self._task = asyncio.create_task(self.run(), name=self.name)

    async def run(self) -> None:
        """Run the worker as a coroutine."""
        if self.running:
            return
        self.running = True
        pubsub = self.pubsub
        last_was_ok = True
        while pubsub.subscribed:
            try:
                await pubsub.get_message(ignore_subscribe_messages=True, timeout=1)
                if not last_was_ok:
                    _LOG.info("Redis is back")
                    last_was_ok = True
            except redis.exceptions.RedisError:
                if last_was_ok:
                    _LOG.warning("Redis connection problem")
                last_was_ok = False
                await asyncio.sleep(0.5)
            except Exception:  # pylint: disable=broad-exception-caught
                _LOG.warning("Unexpected error", exc_info=True)
        _LOG.info("Redis subscription worker stopped")
        pubsub.close()
        self.running = False
        self._task = None

    async def stop(self) -> None:
        """Stop the worker."""
        # Stopping simply unsubscribes from all channels and patterns.
        # The unsubscribe responses that are generated will short circuit
        # the loop in run(), calling pubsub.close() to clean up the connection
        self.pubsub.unsubscribe()
        self.pubsub.punsubscribe()
        # Wait for the task to complete if it's running
        if self._task is not None:
            await self._task


class RedisBroadcaster(interface.BaseBroadcaster):
    """Implement broadcasting messages using Redis."""

    _worker: AsyncPubSubWorker = None  # type: ignore[assignment]

    def __init__(
        self,
        broadcast_prefix: str,
        master: "redis.asyncio.client.Redis",
        slave: "redis.asyncio.client.Redis",
    ) -> None:
        """Initialize the broadcaster."""
        self._master = master
        self._slave = slave
        self._broadcast_prefix = broadcast_prefix

        self._pub_sub = self._master.pubsub(ignore_subscribe_messages=True)

    async def init(self) -> None:
        """Initialize the broadcaster."""

        # Need to be subscribed to something for the worker to stay alive
        await self._pub_sub.subscribe(**{self._get_channel("c2c_dummy"): lambda _: None})
        self._worker = AsyncPubSubWorker(self._pub_sub, name="c2c_broadcast_listener")
        await self._worker.start()

    def _get_channel(self, channel: str) -> str:
        return self._broadcast_prefix + channel

    async def subscribe(self, channel: str, callback: Callable[..., Awaitable[Any]]) -> None:
        """Subscribe to a channel."""

        async def wrapper(message: Mapping[str, Any]) -> None:
            _LOG.debug("Received a broadcast on %s: %s", message["channel"], repr(message["data"]))
            data = json.loads(message["data"])
            try:
                response = await callback(**data["params"])
            except Exception as e:  # pragma: no cover  # pylint: disable=broad-exception-caught
                _LOG.error("Failed handling a broadcast message", exc_info=True)
                response = {"status": 500, "message": str(e)}
            answer_channel = data.get("answer_channel")
            if answer_channel is not None:
                _LOG.debug("Sending broadcast answer on %s", answer_channel)
                await self._master.publish(answer_channel, json.dumps(utils.add_host_info(response)))

        actual_channel = self._get_channel(channel)
        _LOG.debug("Subscribing %s.%s to %s", callback.__module__, callback.__name__, actual_channel)
        await self._pub_sub.subscribe(**{actual_channel: wrapper})

    async def unsubscribe(self, channel: str) -> None:
        """Unsubscribe from a channel."""
        _LOG.debug("Unsubscribing from %s", channel)
        actual_channel = self._get_channel(channel)
        await self._pub_sub.unsubscribe(actual_channel)

    async def broadcast(
        self,
        channel: str,
        params: Mapping[str, Any],
        expect_answers: bool,
        timeout: float,
    ) -> list[Any] | None:
        """Broadcast a message to all the listeners."""
        _LOG.debug("Broadcasting on %s with params: %s", channel, params)
        if expect_answers:
            return await self._broadcast_with_answer(channel, params, timeout)
        await self._broadcast(channel, {"params": params})
        return None

    async def _broadcast_with_answer(
        self,
        channel: str,
        params: Mapping[str, Any] | None,
        timeout: float,
    ) -> list[Any]:
        answers = []

        # Make sure the worker is running
        assert self._worker.running

        async def callback(msg: Mapping[str, Any]) -> None:
            _LOG.debug("Received a broadcast answer on %s", msg["channel"])
            answers.append(json.loads(msg["data"]))

        answer_channel = self._get_channel(channel) + "".join(
            random.choice(string.ascii_uppercase + string.digits)  # noqa: S311 # nosec
            for _ in range(10)
        )
        _LOG.debug("Subscribing for broadcast answers on %s", answer_channel)
        await self._pub_sub.subscribe(**{answer_channel: callback})
        message = {"params": params, "answer_channel": answer_channel}

        try:
            nb_received = await self._broadcast(channel, message)

            # Wait for responses with timeout
            start_time = asyncio.get_event_loop().time()
            while len(answers) < nb_received:
                remaining = timeout - (asyncio.get_event_loop().time() - start_time)
                if remaining <= 0:
                    _LOG.warning(
                        "timeout waiting for %d/%d answers on %s",
                        len(answers),
                        nb_received,
                        answer_channel,
                    )
                    # Fill in missing answers with None
                    while len(answers) < nb_received:
                        answers.append(None)
                    return answers

                # Wait a short time for more messages to arrive
                await asyncio.sleep(min(0.1, remaining))
            return answers
        finally:
            await self._pub_sub.unsubscribe(answer_channel)

    async def _broadcast(self, channel: str, message: Mapping[str, Any]) -> int:
        actual_channel = self._get_channel(channel)
        _LOG.debug("Sending a broadcast on %s", actual_channel)
        nb_received = await self._master.publish(actual_channel, json.dumps(message))
        _LOG.debug("Broadcast on %s sent to %d listeners", actual_channel, nb_received)
        assert isinstance(nb_received, int), "Expected nb_received to be an int"
        return nb_received

    async def copy_local_subscriptions(self, prev_broadcaster: local.LocalBroadcaster) -> None:
        """Copy the subscriptions from a local broadcaster."""
        for channel, callback in prev_broadcaster.get_subscribers().items():
            await self.subscribe(channel, callback)
