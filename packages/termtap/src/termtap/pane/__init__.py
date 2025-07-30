"""Pane module - everything happens in panes.

PUBLIC API:
  - Pane: The fundamental data class
  - send_command: Execute commands in a pane
  - interrupt: Send interrupt signal
"""

from .core import Pane
from .execution import send_command, interrupt

__all__ = ["Pane", "send_command", "interrupt"]
