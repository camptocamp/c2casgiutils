import os
import socket
from typing import Any, TypedDict


class _BroadcastResponse(TypedDict):
    """Wrapper for broadcast responses."""

    hostname: str
    pid: int
    payload: Any


def add_host_info(response: Any) -> _BroadcastResponse:
    """Add information related to the host."""
    return {
        "hostname": socket.gethostname(),
        "pid": os.getpid(),
        "payload": response,
    }
