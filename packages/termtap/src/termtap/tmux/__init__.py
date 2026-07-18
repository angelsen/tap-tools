"""Pure tmux operations - shared utilities for all tmux modules.

PUBLIC API:
  - run_tmux: Run tmux command and return result
  - list_panes: List panes with filtering
  - get_pane: Get single pane by ID
  - send_keys: Send keystrokes to pane
  - paste_text: Paste text into pane via buffer (for commands)
  - capture_pane: Capture all pane content (history + visible)
  - validate_pane_id: Validate pane ID format and existence
  - build_client_context: Build client context from tmux environment
"""

# Core tmux operations
from .core import run_tmux

# Only essential external functions
from .ops import (
    build_client_context,
    get_pane,
    list_panes,
    send_keys,
    paste_text,
    capture_pane,
)

from .resolution import validate_pane_id

__all__ = [
    "run_tmux",
    "list_panes",
    "get_pane",
    "send_keys",
    "paste_text",
    "capture_pane",
    "validate_pane_id",
    "build_client_context",
]
