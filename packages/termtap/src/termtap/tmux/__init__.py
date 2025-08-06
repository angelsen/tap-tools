"""Tmux operations module - pane-first architecture.

Provides pane-centric tmux operations with streaming support.
Sessions are containers for organizing panes.

PUBLIC API:
  Exceptions:
    - TmuxError: Base exception for tmux operations
    - CurrentPaneError: Forbidden operation on current pane
    - SessionNotFoundError: Session not found

  Core Operations:
    - run_tmux: Execute tmux commands
    - check_tmux_available: Check if tmux is available
    - get_current_pane: Get current pane ID

  Session Management:
    - SessionInfo: Session information
    - session_exists: Check if session exists
    - create_session: Create new detached session
    - new_session: Create session with optional attach
    - kill_session: Kill a session
    - attach_session: Attach to session
    - list_sessions: List all sessions
    - get_or_create_session: Get or create session

  Pane Operations:
    - PaneInfo: Pane information
    - send_keys: Send keystrokes to pane
    - send_via_paste_buffer: Send content via paste buffer (multiline/special chars)
    - get_pane_pid: Get pane process PID
    - get_pane_session_window_pane: Get session:window.pane format
    - get_pane_info: Get pane details
    - list_panes: List panes with filtering
    - capture_visible: Capture visible content
    - capture_all: Capture all history
    - capture_last_n: Capture last N lines
    - create_panes_with_layout: Create panes with layout
    - apply_layout: Apply layout to window

  Target Resolution:
    - resolve_target: Resolve target to one or more panes
    - resolve_target_to_pane: Resolve target to pane ID
    - resolve_or_create_target: Resolve or create target

  Structure Creation:
    - get_or_create_session_with_structure: Create complex structures

  Streaming:
    - Stream: Stream handler for pane output
    - Stream: Stream pane output to files

  Utilities:
    - generate_session_name: Generate Docker-style names
"""

# Exceptions
from .exceptions import (
    TmuxError,
    CurrentPaneError,
    SessionNotFoundError,
    PaneNotFoundError,
    WindowNotFoundError,
)

# Core operations
from .core import (
    run_tmux,
    check_tmux_available,
    get_current_pane,
)

# Session management
from .session import (
    SessionInfo,
    session_exists,
    create_session,
    new_session,
    kill_session,
    attach_session,
    list_sessions,
    get_or_create_session,
)

# Pane operations
from .pane import (
    PaneInfo,
    send_keys,
    send_via_paste_buffer,
    get_pane_pid,
    get_pane_session_window_pane,
    get_pane_info,
    list_panes,
    capture_visible,
    capture_all,
    capture_last_n,
    create_panes_with_layout,
    apply_layout,
)

# Target resolution
from .resolution import (
    resolve_target,
    resolve_target_to_pane,
    resolve_or_create_target,
)

# Structure creation
from .structure import (
    get_or_create_session_with_structure,
)

# Streaming
from .stream import (
    Stream,
    StreamManager,  # Temporary - to be removed
)

# Utilities
from .names import (
    generate_session_name,
)

__all__ = [
    # Exceptions
    "TmuxError",
    "CurrentPaneError",
    "SessionNotFoundError",
    "PaneNotFoundError",
    "WindowNotFoundError",
    # Core
    "run_tmux",
    "check_tmux_available",
    "get_current_pane",
    # Sessions
    "SessionInfo",
    "session_exists",
    "create_session",
    "new_session",
    "kill_session",
    "attach_session",
    "list_sessions",
    "get_or_create_session",
    # Panes
    "PaneInfo",
    "send_keys",
    "send_via_paste_buffer",
    "get_pane_pid",
    "get_pane_session_window_pane",
    "get_pane_info",
    "list_panes",
    "capture_visible",
    "capture_all",
    "capture_last_n",
    "create_panes_with_layout",
    "apply_layout",
    # Resolution
    "resolve_target",
    "resolve_target_to_pane",
    "resolve_or_create_target",
    # Structure
    "get_or_create_session_with_structure",
    # Streaming
    "Stream",
    "StreamManager",  # Temporary
    # Utilities
    "generate_session_name",
]
