"""Pure tmux operations - shared utilities for all tmux modules.

PUBLIC API:
  - run_tmux: Run tmux command and return result
  - get_pane_pid: Get pane process PID
  - get_pane_info: Get pane details
  - list_panes: List panes with filtering
  - send_keys: Send keystrokes to pane
  - capture_visible: Capture visible content
  - create_panes_with_layout: Create multiple panes with layout
  - resolve_target_to_pane: Resolve target to pane ID
  - resolve_or_create_target: Resolve or create target
  - session_exists: Check if session exists
  - create_session: Create new tmux session
  - kill_session: Kill tmux session
"""

# Core tmux operations
from .core import run_tmux

# Only essential external functions
from .pane import (
    get_pane_pid,
    get_pane_info,
    list_panes,
    send_keys,
    capture_visible,
    create_panes_with_layout,
)

from .resolution import (
    resolve_target_to_pane,
    resolve_or_create_target,
)

from .session import (
    session_exists,
    create_session,
    kill_session,
)

__all__ = [
    "run_tmux",
    "get_pane_pid",
    "get_pane_info",
    "list_panes",
    "send_keys",
    "capture_visible",
    "create_panes_with_layout",
    "resolve_target_to_pane",
    "resolve_or_create_target",
    "session_exists",
    "create_session",
    "kill_session",
]
