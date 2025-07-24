"""Session management for tmux.

This module provides functions for managing tmux sessions including
creating, listing, and sending commands to sessions.
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
    def _from_format_line(cls, line: str) -> "SessionInfo":
        """Parse from tmux format string."""
        parts = _parse_format_line(line)
        return cls(
            name=parts["0"], created=parts.get("1", ""), attached=parts.get("2", "0")
        )


def _session_exists(name: str) -> bool:
    """Check if session exists."""
    code, _, _ = _run_tmux(["has-session", "-t", name])
    return code == 0


def _create_session(name: str, start_dir: Optional[str] = None) -> bool:
    """Create new detached session."""
    args = ["new-session", "-d", "-s", name]
    if start_dir:
        args.extend(["-c", start_dir])
    code, _, _ = _run_tmux(args)
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
        info = SessionInfo._from_format_line(line)
        sessions.append(info)

    return sessions


def get_or_create_session(
    target: Optional[str] = None, start_dir: Optional[str] = None
) -> str:
    """Get existing or create new session.

    Args:
        target: Session name. If None, generates Docker-style name.
        start_dir: Starting directory for new session.

    Returns:
        Session name.
    """
    if target is None:
        from .names import _generate_session_name

        while True:
            name = _generate_session_name()
            if not _session_exists(name):
                break
    else:
        name = target

    if not _session_exists(name):
        _create_session(name, start_dir)
    return name


def send_keys(session: str, command: str, enter: bool = True) -> bool:
    """Send keystrokes to a session.

    Args:
        session: Target session name.
        command: Command text to send.
        enter: Whether to send Enter key after command.

    Returns:
        True if keys were sent successfully, False otherwise.

    Raises:
        CurrentPaneError: If attempting to send to current pane.
    """
    from .utils import _is_current_pane

    if _is_current_pane(session):
        raise CurrentPaneError(
            f"Cannot send commands to current pane ({session}). "
            "Use a different target session."
        )

    # Don't escape - send raw command
    # This allows us to send complex commands like: bash -c 'echo "test"'
    args = ["send-keys", "-t", session, command]
    if enter:
        args.append("Enter")
    code, _, _ = _run_tmux(args)
    return code == 0
