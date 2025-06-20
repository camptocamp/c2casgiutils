import os
import socket
from typing import Any


def add_host_info(response: Any) -> Any:
    """Add information related to the host."""
    if isinstance(response, dict):
        return {**response, "hostname": socket.gethostname(), "pid": os.getpid()}
    return response
