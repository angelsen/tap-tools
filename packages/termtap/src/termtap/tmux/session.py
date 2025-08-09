"""Session management - pure session operations.

PUBLIC API:
  - session_exists: Check if session exists
  - create_session: Create new tmux session
  - kill_session: Kill tmux session
"""

from typing import Optional, NamedTuple, List

from .core import run_tmux, _parse_format_line
from .names import _generate_session_name


class SessionInfo(NamedTuple):
    """Session information.

    Attributes:
        name: Session name.
        created: Creation timestamp.
        attached: Attachment status.
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
        name: Session name.

    Returns:
        True if session exists.
    """
    code, _, _ = run_tmux(["has-session", "-t", name])
    return code == 0


def create_session(name: str, start_dir: str = ".") -> tuple[str, str]:
    """Create a new detached session.

    Args:
        name: Session name.
        start_dir: Starting directory. Defaults to '.'.

    Returns:
        Tuple of (pane_id, session:window.pane).

    Raises:
        RuntimeError: If session creation fails.
    """
    args = ["new-session", "-d", "-s", name, "-c", start_dir]
    code, _, stderr = run_tmux(args)

    if code != 0:
        raise RuntimeError(f"Failed to create session: {stderr}")

    code, stdout, _ = run_tmux(["list-panes", "-t", f"{name}:0.0", "-F", "#{pane_id}"])
    if code != 0:
        raise RuntimeError("Failed to get pane ID for new session")

    pane_id = stdout.strip()
    return pane_id, f"{name}:0.0"


def __new_session(name: str, start_dir: str = ".", attach: bool = False) -> tuple[str, str]:
    """Create new session with window and pane.

    Args:
        name: Session name.
        start_dir: Starting directory.
        attach: Whether to attach to session.
    """
    if attach:
        args = ["new-session", "-s", name, "-c", start_dir, "-P", "-F", "#{pane_id}"]
        code, stdout, stderr = run_tmux(args)

        if code != 0:
            raise RuntimeError(f"Failed to create session: {stderr}")

        pane_id = stdout.strip()
        return pane_id, f"{name}:0.0"
    else:
        return create_session(name, start_dir)


def kill_session(name: str) -> bool:
    """Kill a tmux session.

    Args:
        name: Session name.

    Returns:
        True if successful.
    """
    code, _, _ = run_tmux(["kill-session", "-t", name])
    return code == 0


def __attach_session(name: str) -> bool:
    """Attach to a tmux session.

    Args:
        name: Session name.
    """
    code, _, _ = run_tmux(["attach-session", "-t", name])
    return code == 0


def _list_sessions() -> List[SessionInfo]:
    """List all tmux sessions."""
    code, stdout, _ = run_tmux(["list-sessions", "-F", "#{session_name}:#{session_created}:#{session_attached}"])

    if code != 0:
        return []

    sessions = []
    for line in stdout.strip().split("\n"):
        if line:
            sessions.append(SessionInfo.from_format_line(line))

    return sessions


def _get_or_create_session(
    target: Optional[str] = None, start_dir: str = "."
) -> tuple[str, Optional[str], Optional[str]]:
    """Get existing or create new session.

    Args:
        target: Target session name. Generates unique name if None.
        start_dir: Starting directory. Defaults to '.'.
    """
    if target is None:
        # Generate unique name
        while True:
            name = _generate_session_name()
            if not session_exists(name):
                break
    else:
        name = target

    if not session_exists(name):
        pane_id, swp = create_session(name, start_dir)
        return name, pane_id, swp

    return name, None, None
