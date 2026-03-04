from typing import Generic, TypeVar

from pydantic import BaseModel

_BroadcastResponse = TypeVar("_BroadcastResponse")


class BroadcastResponse(BaseModel, Generic[_BroadcastResponse]):
    """Broadcast response model."""

    hostname: str
    pid: int
    payload: _BroadcastResponse
