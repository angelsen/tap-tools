"""Tmux operations module - pane-first architecture.

Provides pane-centric tmux operations with streaming support.
Sessions are containers for organizing panes.

PUBLIC API:
  - TmuxError, CurrentPaneError, SessionNotFoundError: Exception types
  - SessionInfo: Session information dataclass
  - session_exists: Check if session exists
  - kill_session: Kill a session
  - new_session: Create new session
  - attach_session: Attach to session
  - list_sessions: List all sessions
  - get_or_create_session: Get existing or create new session
  - generate_session_name: Generate Docker-style session names
  - send_keys: Send keystrokes to pane
  - capture_visible: Capture visible pane content
  - capture_all: Capture all pane history
  - capture_last_n: Capture last N lines
  - get_pane_pid: Get PID for a pane
  - resolve_target_to_pane: Resolve any target to pane ID
  - list_panes: List panes with filtering options
  - get_pane_info: Get detailed info for a pane
  - PaneInfo: Complete pane information dataclass
"""

from .exceptions import (
    TmuxError,
    CurrentPaneError,
    SessionNotFoundError,
)

from .session import (
    SessionInfo,
    session_exists,
    kill_session,
    new_session,
    attach_session,
    list_sessions,
    get_or_create_session,
    send_keys,
)

from .names import (
    generate_session_name,
)

from .pane import (
    capture_visible,
    capture_all,
    capture_last_n,
)

from .utils import (
    get_pane_pid,
    resolve_target_to_pane,
    list_panes,
    get_pane_info,
    PaneInfo,
)

__all__ = [
    "TmuxError",
    "CurrentPaneError",
    "SessionNotFoundError",
    "SessionInfo",
    "session_exists",
    "kill_session",
    "new_session",
    "attach_session",
    "list_sessions",
    "get_or_create_session",
    "generate_session_name",
    "send_keys",
    "capture_visible",
    "capture_all",
    "capture_last_n",
    "get_pane_pid",
    "resolve_target_to_pane",
    "list_panes",
    "get_pane_info",
    "PaneInfo",
]
