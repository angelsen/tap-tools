"""Pure tmux operations - shared utilities for all tmux modules.

PUBLIC API:
  - get_pane_pid: Get pane process PID
  - get_pane_info: Get pane details
  - list_panes: List panes with filtering
  - send_keys: Send keystrokes to pane
  - capture_visible: Capture visible content
  - resolve_target_to_pane: Resolve target to pane ID
  - resolve_or_create_target: Resolve or create target
"""

# Only essential external functions
from .pane import (
    get_pane_pid,
    get_pane_info,
    list_panes,
    send_keys,
    capture_visible,
)

from .resolution import (
    resolve_target_to_pane,
    resolve_or_create_target,
)

__all__ = [
    "get_pane_pid",
    "get_pane_info",
    "list_panes",
    "send_keys",
    "capture_visible",
    "resolve_target_to_pane",
    "resolve_or_create_target",
]
