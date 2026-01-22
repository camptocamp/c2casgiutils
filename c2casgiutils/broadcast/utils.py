import os
import socket
from typing import Generic, TypeVar

from pydantic import BaseModel

_BroadcastResponse = TypeVar("_BroadcastResponse")


class BroadcastResponse(BaseModel, Generic[_BroadcastResponse]):
    """Broadcast response model."""

    hostname: str
    pid: int
    payload: _BroadcastResponse


def add_host_info(response: _BroadcastResponse) -> BroadcastResponse[_BroadcastResponse]:
    """Add information related to the host."""
    return BroadcastResponse(
        hostname=socket.gethostname(),
        pid=os.getpid(),
        payload=response,
    )
