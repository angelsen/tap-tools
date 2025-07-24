"""Public tmux API - re-exports from submodules.

PURPOSE: Low-level tmux operations for session management and pane capture.

PUBLIC API:
  - list_sessions: Get all tmux sessions
  - SessionInfo: Session information named tuple
  - kill_session: Kill a tmux session
  - get_or_create_session: Get existing or create new session
  - send_keys: Send keystrokes to a session
  - capture_visible: Capture visible pane content
  - capture_all: Capture entire pane history
  - capture_last_n: Capture last N lines from pane
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

__all__ = [
    "TmuxError",
    "CurrentPaneError",
    "SessionNotFoundError",
    "SessionInfo",
    "kill_session",
    "list_sessions",
    "get_or_create_session",
    "send_keys",
    "capture_visible",
    "capture_all",
    "capture_last_n",
]
