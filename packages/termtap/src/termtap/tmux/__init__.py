"""Pure tmux operations - shared utilities for all tmux modules.

PUBLIC API:
  - run_tmux: Run tmux command and return result
  - list_panes: List panes with filtering
  - get_pane: Get single pane by ID
  - get_pane_pid: Get pane process PID
  - send_keys: Send keystrokes to pane
  - send_via_paste_buffer: Send content using paste buffer
  - capture_visible: Capture visible content
  - capture_last_n: Capture last N lines from pane
  - create_panes_with_layout: Create multiple panes with layout
  - resolve_target: Resolve target to pane_id
"""

# Core tmux operations
from .core import run_tmux

# Only essential external functions
from .ops import (
    get_pane,
    get_pane_pid,
    list_panes,
    send_keys,
    send_via_paste_buffer,
    capture_visible,
    capture_last_n,
    create_panes_with_layout,
)

from .resolution import resolve_target

__all__ = [
    "run_tmux",
    "list_panes",
    "get_pane",
    "get_pane_pid",
    "send_keys",
    "send_via_paste_buffer",
    "capture_visible",
    "capture_last_n",
    "create_panes_with_layout",
    "resolve_target",
]
