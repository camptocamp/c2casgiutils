import os
import socket
from typing import TypeVar

from c2casgiutils.broadcast.types import BroadcastResponse

_BroadcastResponse = TypeVar("_BroadcastResponse")


def add_host_info(response: _BroadcastResponse) -> BroadcastResponse[_BroadcastResponse]:
    """Add information related to the host."""
    return BroadcastResponse(
        hostname=socket.gethostname(),
        pid=os.getpid(),
        payload=response,
    )
