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

# Utils
from .utils import (
    run_tmux,
    parse_format_line,
    check_tmux_available,
    get_current_pane,
    is_current_pane,
)

# Session management
from .session import (
    SessionInfo,
    session_exists,
    create_session,
    kill_session,
    list_sessions,
    get_or_create_session,
    send_keys,
)

# Pane operations (read-only)
from .pane import (
    capture_pane,
    capture_visible,
    capture_all,
    capture_last_n,
)

# Name generation
from .names import generate_session_name

__all__ = [
    # Utils
    "run_tmux",
    "parse_format_line", 
    "check_tmux_available",
    "get_current_pane",
    "is_current_pane",
    # Session
    "SessionInfo",
    "session_exists",
    "create_session",
    "kill_session",
    "list_sessions",
    "get_or_create_session",
    "send_keys",
    # Capture
    "capture_pane",
    "capture_visible",
    "capture_all",
    "capture_last_n",
    # Names
    "generate_session_name",
]