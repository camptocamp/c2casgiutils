import pytest

from c2casgiutils import broadcast
from c2casgiutils.broadcast import local


@pytest.fixture
async def local_broadcaster():
    broadcast._broadcaster = local.LocalBroadcaster()  # pylint: disable=W0212
    try:
        # Initialize the broadcaster
        await broadcast._broadcaster.init()  # pylint: disable=W0212
        yield
    finally:
        broadcast._broadcaster = None  # pylint: disable=W0212


@pytest.mark.asyncio
async def test_local(local_broadcaster):
    cb_calls = [0, 0]

    async def cb1(data):
        cb_calls[0] += 1
        return data + 1

    async def cb2():
        cb_calls[1] += 1

    assert await broadcast.broadcast("test1", {"data": 1}, expect_answers=True) == []
    assert cb_calls == [0, 0]

    await broadcast.subscribe("test1", cb1)
    await broadcast.subscribe("test2", cb2)
    assert cb_calls == [0, 0]

    assert await broadcast.broadcast("test1", {"data": 1}) is None
    assert cb_calls == [1, 0]

    assert await broadcast.broadcast("test2") is None
    assert cb_calls == [1, 1]

    assert await broadcast.broadcast("test1", {"data": 12}, expect_answers=True) == [13]
    assert cb_calls == [2, 1]

    await broadcast.unsubscribe("test1")
    assert await broadcast.broadcast("test1", {"data": 1}, expect_answers=True) == []
    assert cb_calls == [2, 1]


@pytest.mark.asyncio
async def test_decorator(local_broadcaster):
    cb_calls = [0, 0]

    async def cb1_(value):
        cb_calls[0] += 1
        return value + 1

    cb1 = await broadcast.decorate(cb1_, expect_answers=True)

    async def cb2_():
        cb_calls[1] += 1

    cb2 = await broadcast.decorate(cb2_, channel="test3")

    assert await cb1(value=12) == [13]
    assert cb_calls == [1, 0]

    assert await cb2() is None
    assert cb_calls == [1, 1]


@pytest.mark.asyncio
async def test_fallback():
    cb_calls = [0]

    async def cb1(value):
        cb_calls[0] += 1
        return value + 1

    try:
        await broadcast.subscribe("test1", cb1)

        assert await broadcast.broadcast("test1", {"value": 12}, expect_answers=True) == [13]
        assert cb_calls == [1]
    finally:
        broadcast._broadcaster = None  # pylint: disable=W0212
