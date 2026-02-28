import pytest
import pytest_asyncio
from pydantic import BaseModel

from c2casgiutils import broadcast
from c2casgiutils.broadcast import local


@pytest_asyncio.fixture
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

    result = await broadcast.broadcast("test1", {"data": 12}, expect_answers=True)
    assert len(result) == 1
    assert result[0].payload == 13
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

    result = await cb1(value=12)
    assert len(result) == 1
    assert result[0].payload == 13
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

        result = await broadcast.broadcast("test1", {"value": 12}, expect_answers=True)
        assert len(result) == 1
        assert result[0].payload == 13
        assert cb_calls == [1]
    finally:
        broadcast._broadcaster = None  # pylint: disable=W0212


def test_get_return_type():
    """Test _get_return_type function."""

    # Test with simple return type
    def func_simple() -> int:
        return 42

    assert broadcast._get_return_type(func_simple) is int

    # Test with Awaitable return type
    async def func_awaitable() -> str:
        return "test"

    return_type = broadcast._get_return_type(func_awaitable)
    assert return_type is str

    # Test with no return type annotation
    def func_no_annotation():
        return None

    assert broadcast._get_return_type(func_no_annotation) is None

    # Test with None return type
    def func_none() -> None:
        pass

    assert broadcast._get_return_type(func_none) is type(None)


class _PayloadModel(BaseModel):
    value: int


def test_serialize_params():
    params = {
        "model": _PayloadModel(value=3),
        "plain": "ok",
        "number": 7,
    }

    serialized = broadcast._serialize_params(params)

    assert serialized["model"] == {"value": 3}
    assert serialized["plain"] == "ok"
    assert serialized["number"] == 7


def test_deserialize_payload():
    payload = {"value": 9}

    result = broadcast._deserialize_payload(payload, _PayloadModel)
    assert isinstance(result, _PayloadModel)
    assert result.value == 9

    assert broadcast._deserialize_payload(payload, None) == payload
    assert broadcast._deserialize_payload(payload, int) == payload


def test_deserialize_kwargs():
    def func(model: _PayloadModel, plain: str) -> None:
        del model
        del plain

    kwargs = {"model": {"value": 5}, "plain": "ok", "extra": 1}
    deserialized = broadcast._deserialize_kwargs(kwargs, func)

    assert isinstance(deserialized["model"], _PayloadModel)
    assert deserialized["model"].value == 5
    assert deserialized["plain"] == "ok"
    assert deserialized["extra"] == 1
