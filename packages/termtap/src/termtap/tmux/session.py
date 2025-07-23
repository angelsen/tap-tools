"""tmux session management - depends only on utils."""
from typing import Optional, NamedTuple, List
from .utils import run_tmux, parse_format_line
from .exceptions import CurrentPaneError


class SessionInfo(NamedTuple):
    """tmux session information."""
    name: str
    created: str
    attached: str
    
    @classmethod
    def from_format_line(cls, line: str) -> "SessionInfo":
        """Parse from tmux format string."""
        parts = parse_format_line(line)
        return cls(
            name=parts['0'],
            created=parts.get('1', ''),
            attached=parts.get('2', '0')
        )


def session_exists(name: str) -> bool:
    """Check if session exists."""
    code, _, _ = run_tmux(["has-session", "-t", name])
    return code == 0


def create_session(name: str, start_dir: Optional[str] = None) -> bool:
    """Create new detached session."""
    args = ["new-session", "-d", "-s", name]
    if start_dir:
        args.extend(["-c", start_dir])
    code, _, _ = run_tmux(args)
    return code == 0


def kill_session(name: str) -> bool:
    """Kill a session."""
    code, _, _ = run_tmux(["kill-session", "-t", name])
    return code == 0


def list_sessions() -> List[SessionInfo]:
    """List all tmux sessions."""
    code, out, _ = run_tmux([
        "list-sessions", "-F", 
        "#{session_name}:#{session_created}:#{session_attached}"
    ])
    
    if code != 0 or not out.strip():
        return []
    
    sessions = []
    for line in out.strip().split('\n'):
        info = SessionInfo.from_format_line(line)
        sessions.append(info)
    
    return sessions


def get_or_create_session(target: Optional[str] = None, start_dir: Optional[str] = None) -> str:
    """Get existing session or create new one.
    
    Args:
        target: Session name. If None, generates Docker-style name
        start_dir: Starting directory for new session
        
    Returns:
        Session name
    """
    if target is None:
        from .names import generate_session_name
        # Generate unique name
        while True:
            name = generate_session_name()
            if not session_exists(name):
                break
    else:
        name = target
        
    if not session_exists(name):
        create_session(name, start_dir)
    return name


def send_keys(session: str, command: str, enter: bool = True) -> bool:
    """Send keys to session.
    
    Raises:
        CurrentPaneError: If attempting to send to current pane
    """
    from .utils import is_current_pane
    
    # Safety check: prevent sending to current pane
    if is_current_pane(session):
        raise CurrentPaneError(
            f"Cannot send commands to current pane ({session}). "
            "Use a different target session."
        )
    
    # Don't escape - send raw command
    # This allows us to send complex commands like: bash -c 'echo "test"'
    args = ["send-keys", "-t", session, command]
    if enter:
        args.append("Enter")
    code, _, _ = run_tmux(args)
    return code == 0