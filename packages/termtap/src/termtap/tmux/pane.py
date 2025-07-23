"""tmux output capture - depends only on utils."""
from typing import Optional
from .utils import run_tmux


def capture_pane(session: str, lines: Optional[int] = None) -> str:
    """Capture pane output from session.
    
    Args:
        session: Session name
        lines: Number of lines to capture (None = visible, -1 = all history)
        
    Returns:
        Captured output as string
    """
    args = ["capture-pane", "-t", session, "-p"]
    
    if lines is not None:
        if lines == -1:
            # Full scrollback history
            args.extend(["-S", "-"])
        else:
            # Last N lines
            args.extend(["-S", f"-{lines}"])
    
    code, out, _ = run_tmux(args)
    return out if code == 0 else ""


def capture_visible(session: str) -> str:
    """Capture only visible content."""
    return capture_pane(session, lines=None)


def capture_all(session: str) -> str:
    """Capture full scrollback history."""
    return capture_pane(session, lines=-1)


def capture_last_n(session: str, n: int) -> str:
    """Capture last N lines."""
    return capture_pane(session, lines=n)