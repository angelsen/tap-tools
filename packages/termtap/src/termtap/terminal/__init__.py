"""Terminal emulation module.

PUBLIC API:
  - LineBuffer: Single line with cursor position for overwrites
  - SlimScreen: pyte-compatible screen with ring buffer
  - PaneTerminal: Per-pane state (SlimScreen + stream + action)
  - PaneManager: Manages all PaneTerminals
"""

from .line_buffer import LineBuffer
from .slim_screen import SlimScreen
from .pane_terminal import PaneTerminal
from .manager import PaneManager

__all__ = [
    "LineBuffer",
    "SlimScreen",
    "PaneTerminal",
    "PaneManager",
]
