"""Pane capture operations for tmux.

PUBLIC API:
  - capture_visible: Capture visible pane content
  - capture_all: Capture entire pane history
  - capture_last_n: Capture last N lines from pane
"""

from typing import Optional
from ..types import Target
from .utils import _run_tmux, _is_current_pane
from .exceptions import CurrentPaneError


def _capture_pane(target: Target, lines: Optional[int] = None) -> str:
    """Capture pane output from target.

    Args:
        target: Target specification (session, pane ID, window ID, or session:window.pane)
        lines: Number of lines to capture (None = visible, -1 = all history)

    Returns:
        Captured output as string

    Raises:
        CurrentPaneError: If attempting to capture from current pane.
    """
    if _is_current_pane(target):
        raise CurrentPaneError(f"Cannot capture from current pane ({target}). Use a different target.")

    args = ["capture-pane", "-t", target, "-p"]

    if lines is not None:
        if lines == -1:
            # Full scrollback history
            args.extend(["-S", "-"])
        else:
            # Last N lines
            args.extend(["-S", f"-{lines}"])

    code, out, _ = _run_tmux(args)
    if code != 0:
        return ""
    
    # Strip trailing empty lines that tmux adds to fill the pane height
    # This preserves empty lines within the content but removes padding
    lines_list = out.splitlines()
    while lines_list and not lines_list[-1].strip():
        lines_list.pop()
    
    # Reconstruct with original line endings
    return '\n'.join(lines_list) + '\n' if lines_list else ""


def capture_visible(target: Target) -> str:
    """Capture visible pane content.

    Args:
        target: Target specification (session, pane ID, window ID, or session:window.pane).

    Returns:
        Visible pane content as string.
    """
    return _capture_pane(target, lines=None)


def capture_all(target: Target) -> str:
    """Capture entire pane history.

    Args:
        target: Target specification (session, pane ID, window ID, or session:window.pane).

    Returns:
        Full pane history including scrollback as string.
    """
    return _capture_pane(target, lines=-1)


def capture_last_n(target: Target, n: int) -> str:
    """Capture last N lines from pane.

    Args:
        target: Target specification (session, pane ID, window ID, or session:window.pane).
        n: Number of lines to capture.

    Returns:
        Last N lines from pane as string.
    """
    return _capture_pane(target, lines=n)
