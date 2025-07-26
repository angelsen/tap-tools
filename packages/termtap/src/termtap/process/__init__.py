"""Process detection and state inspection for termtap.

PUBLIC API:
- is_ready: Check if a tmux session is ready for commands
- wait_until_ready: Wait for a process to become ready
- get_process_info: Get detailed process information
"""

from .detector import is_ready, wait_until_ready, get_process_info

__all__ = [
    "is_ready",
    "wait_until_ready",
    "get_process_info",
]
