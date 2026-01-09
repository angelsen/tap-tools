"""Port utilities for webtap services.

PUBLIC API:
  - is_port_available: Check if port can be bound
  - find_available_port: Find first available port in range
"""

import socket

BASE_PORT = 37650
MAX_TRIES = 20


def is_port_available(port: int) -> bool:
    """Check if port is available (can bind)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def find_available_port(start: int = BASE_PORT, max_tries: int = MAX_TRIES) -> int | None:
    """Find first available port in range [start, start+max_tries)."""
    for port in range(start, start + max_tries):
        if is_port_available(port):
            return port
    return None


__all__ = ["is_port_available", "find_available_port", "BASE_PORT", "MAX_TRIES"]
