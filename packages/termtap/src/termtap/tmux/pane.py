"""Pane capture operations for tmux.

PUBLIC API:
  - capture_visible: Capture visible pane content
  - capture_all: Capture entire pane history
  - capture_last_n: Capture last N lines from pane

PACKAGE API: (none)

PRIVATE:
  - _capture_pane: Internal capture implementation
"""

from typing import Optional
from .utils import _run_tmux


def _capture_pane(session: str, lines: Optional[int] = None) -> str:
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

    code, out, _ = _run_tmux(args)
    return out if code == 0 else ""


def capture_visible(session: str) -> str:
    """Capture visible pane content.

    Args:
        session: Target session name.

    Returns:
        Visible pane content as string.
    """
    return _capture_pane(session, lines=None)


def capture_all(session: str) -> str:
    """Capture entire pane history.

    Args:
        session: Target session name.

    Returns:
        Full pane history including scrollback as string.
    """
    return _capture_pane(session, lines=-1)


def capture_last_n(session: str, n: int) -> str:
    """Capture last N lines from pane.

    Args:
        session: Target session name.
        n: Number of lines to capture.

    Returns:
        Last N lines from pane as string.
    """
    return _capture_pane(session, lines=n)
