"""Session management for tmux.

PUBLIC API:
  - SessionInfo: Session information named tuple
  - session_exists: Check if session exists
  - kill_session: Kill a tmux session
  - list_sessions: Get all tmux sessions
  - get_or_create_session: Get existing or create new session
  - send_keys: Send keystrokes to a session
"""

from typing import Optional, NamedTuple, List
from .utils import _run_tmux, _parse_format_line
from .exceptions import CurrentPaneError


class SessionInfo(NamedTuple):
    """Session information named tuple.

    Attributes:
        name: Session name.
        created: Creation timestamp.
        attached: Number of attached clients.
    """

    name: str
    created: str
    attached: str

    @classmethod
    def from_format_line(cls, line: str) -> "SessionInfo":
        """Parse from tmux format string."""
        parts = _parse_format_line(line)
        return cls(name=parts["0"], created=parts.get("1", ""), attached=parts.get("2", "0"))


def session_exists(name: str) -> bool:
    """Check if session exists.

    Args:
        name: Session name to check.

    Returns:
        True if session exists, False otherwise.
    """
    code, _, _ = _run_tmux(["has-session", "-t", name])
    return code == 0


def _create_session(name: str, start_dir: Optional[str] = None) -> tuple[str, str]:
    """Create new detached session and return (pane_id, session:window.pane)."""
    args = ["new-session", "-d", "-s", name, "-P", "-F", "#{pane_id}:#{session_name}:#{window_index}.#{pane_index}"]
    if start_dir:
        args.extend(["-c", start_dir])
    code, stdout, _ = _run_tmux(args)
    if code != 0:
        raise RuntimeError(f"Failed to create session {name}")

    # Parse output like "%42:backend:0.0"
    parts = stdout.strip().split(":")
    pane_id = parts[0]
    swp = ":".join(parts[1:])  # "backend:0.0"
    return pane_id, swp


def new_session(name: str, start_dir: Optional[str] = None, attach: bool = False) -> tuple[str, str]:
    """Create a new tmux session.

    Args:
        name: Session name.
        start_dir: Starting directory for the session.
        attach: Whether to attach to the session after creation.

    Returns:
        Tuple of (pane_id, session:window.pane).
    """
    if attach:
        args = ["new-session", "-s", name, "-P", "-F", "#{pane_id}:#{session_name}:#{window_index}.#{pane_index}"]
        if start_dir:
            args.extend(["-c", start_dir])
        code, stdout, _ = _run_tmux(args)
        if code != 0:
            raise RuntimeError(f"Failed to create session {name}")
        parts = stdout.strip().split(":")
        pane_id = parts[0]
        swp = ":".join(parts[1:])
        return pane_id, swp
    else:
        return _create_session(name, start_dir)


def attach_session(name: str) -> bool:
    """Attach to an existing tmux session.

    Args:
        name: Session name to attach to.

    Returns:
        True if attached successfully.
    """
    code, _, _ = _run_tmux(["attach-session", "-t", name])
    return code == 0


def kill_session(name: str) -> bool:
    """Kill a tmux session.

    Args:
        name: Session name to kill.

    Returns:
        True if session was killed successfully, False otherwise.
    """
    code, _, _ = _run_tmux(["kill-session", "-t", name])
    return code == 0


def list_sessions() -> List[SessionInfo]:
    """Get all tmux sessions.

    Returns:
        List of SessionInfo objects for all active sessions.
    """
    code, out, _ = _run_tmux(
        [
            "list-sessions",
            "-F",
            "#{session_name}:#{session_created}:#{session_attached}",
        ]
    )

    if code != 0 or not out.strip():
        return []

    sessions = []
    for line in out.strip().split("\n"):
        info = SessionInfo.from_format_line(line)
        sessions.append(info)

    return sessions


def get_or_create_session(
    target: Optional[str] = None, start_dir: Optional[str] = None
) -> tuple[str, Optional[str], Optional[str]]:
    """Get existing or create new session.

    Args:
        target: Session name. If None, generates Docker-style name.
        start_dir: Starting directory for new session.

    Returns:
        Tuple of (session_name, pane_id, session:window.pane) where pane_id and swp are None for existing sessions.
    """
    if target is None:
        from .names import generate_session_name

        while True:
            name = generate_session_name()
            if not session_exists(name):
                break
    else:
        name = target

    if not session_exists(name):
        pane_id, swp = _create_session(name, start_dir)
        return name, pane_id, swp
    return name, None, None


def send_keys(target: str, command: str, enter: bool = True) -> bool:
    """Send keystrokes to any tmux target.

    Args:
        target: Target pane (%42), session:window.pane, or session name.
        command: Command text to send.
        enter: Whether to send Enter key after command.

    Returns:
        True if keys were sent successfully, False otherwise.

    Raises:
        CurrentPaneError: If attempting to send to current pane.
    """
    from .utils import _is_current_pane

    if _is_current_pane(target):
        raise CurrentPaneError(f"Cannot send commands to current pane ({target}). Use a different target.")

    # Don't escape - send raw command
    # This allows us to send complex commands like: bash -c 'echo "test"'
    args = ["send-keys", "-t", target, command]
    if enter:
        args.append("Enter")
    code, _, _ = _run_tmux(args)
    return code == 0
