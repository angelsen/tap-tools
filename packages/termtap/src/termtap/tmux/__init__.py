"""Pure tmux operations - shared utilities for all tmux modules.

PUBLIC API:
  - run_tmux: Run tmux command and return result
  - list_panes: List panes with filtering
  - get_pane: Get single pane by ID
  - get_pane_pid: Get pane process PID
  - send_keys: Send keystrokes to pane
  - send_via_paste_buffer: Send content using paste buffer
  - capture_pane: Capture all pane content (history + visible)
  - create_panes_with_layout: Create multiple panes with layout
  - validate_pane_id: Validate pane ID format and existence
  - build_client_context: Build client context from tmux environment
"""

# Core tmux operations
from .core import run_tmux

# Only essential external functions
from .ops import (
    build_client_context,
    get_pane,
    get_pane_pid,
    list_panes,
    send_keys,
    send_via_paste_buffer,
    capture_pane,
    create_panes_with_layout,
)

from .resolution import validate_pane_id

__all__ = [
    "run_tmux",
    "list_panes",
    "get_pane",
    "get_pane_pid",
    "send_keys",
    "send_via_paste_buffer",
    "capture_pane",
    "create_panes_with_layout",
    "validate_pane_id",
    "build_client_context",
]
