"""Tmux operations for session management and pane capture.

PUBLIC API:
  - list_sessions: Get all tmux sessions
  - SessionInfo: Session information named tuple
  - session_exists: Check if a session exists
  - kill_session: Kill a tmux session
  - get_or_create_session: Get existing or create new session
  - send_keys: Send keystrokes to a session
  - capture_visible: Capture visible pane content
  - capture_all: Capture entire pane history
  - capture_last_n: Capture last N lines from pane
  - get_pane_pid: Get PID for a session's pane
  - get_pane_for_session: Get default pane for a session
  - TmuxError: Base exception for tmux operations
  - CurrentPaneError: Raised when targeting current pane
  - SessionNotFoundError: Raised when session doesn't exist
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
    list_sessions,
    get_or_create_session,
    send_keys,
)

from .pane import (
    capture_visible,
    capture_all,
    capture_last_n,
)

from .utils import (
    get_pane_pid,
    get_pane_for_session,
)

__all__ = [
    "TmuxError",
    "CurrentPaneError",
    "SessionNotFoundError",
    "SessionInfo",
    "session_exists",
    "kill_session",
    "list_sessions",
    "get_or_create_session",
    "send_keys",
    "capture_visible",
    "capture_all",
    "capture_last_n",
    "get_pane_pid",
    "get_pane_for_session",
]
