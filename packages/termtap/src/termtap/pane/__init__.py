"""Pane module - everything happens in panes.

PUBLIC API:
  - Pane: The fundamental data class
  - process_scan: Context manager for process scanning
  - send_command: Execute commands in a pane
  - send_keys: Send raw keys to a pane
  - send_interrupt: Send interrupt signal
  - read_output: Read output from a pane
  - get_process_info: Get process information for a pane
"""

from .core import Pane, process_scan
from .execution import send_command, send_keys, send_interrupt
from .inspection import read_output, get_process_info

__all__ = [
    "Pane",
    "process_scan",
    "send_command",
    "send_keys",
    "send_interrupt",
    "read_output",
    "get_process_info",
]
