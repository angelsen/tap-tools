"""Pane module - everything happens in panes.

PUBLIC API:
  - Pane: The fundamental data class
  - process_scan: Context manager for process scanning
  - send_command: Execute commands in a pane
  - send_keys: Send raw keys to a pane
  - send_interrupt: Send interrupt signal
  - read_output: Read output from a pane
  - get_process_info: Get process information for a pane
  - ensure_streaming: Start streaming for a pane
  - mark_command_start: Mark command start for tracking
  - mark_command_end: Mark command completion
  - get_command_output: Get output for specific command
  - read_command_output: Read output for a specific command
  - read_since_last: Read new output since last read
  - read_recent: Read recent output with line limit
"""

from .core import Pane, process_scan
from .execution import send_command, send_keys, send_interrupt
from .inspection import read_output, get_process_info
from .streaming import (
    ensure_streaming,
    mark_command_start,
    mark_command_end,
    get_command_output,
    read_command_output,
    read_since_last,
    read_recent,
)

__all__ = [
    "Pane",
    "process_scan",
    "send_command",
    "send_keys",
    "send_interrupt",
    "read_output",
    "get_process_info",
    "ensure_streaming",
    "mark_command_start",
    "mark_command_end",
    "get_command_output",
    "read_command_output",
    "read_since_last",
    "read_recent",
]
