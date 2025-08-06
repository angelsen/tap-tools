"""Pane inspection functions - read output and get process info."""

from typing import Optional, Any
from .core import Pane


def read_output(pane: Pane, lines: Optional[int] = None, mode: str = "direct") -> str:
    """Read output from pane with automatic filtering.

    Args:
        pane: Target pane
        lines: Number of lines to read (None for visible)
        mode: "direct" (capture-pane) or "stream" (from stream file)
    """
    # Capture output
    if mode == "stream":
        from .streaming import read_recent

        if lines:
            output = read_recent(pane, lines=lines, as_displayed=True)
        else:
            # Default to ~50 lines for "visible"
            output = read_recent(pane, lines=50, as_displayed=True)
    else:
        # Direct capture (default)
        from ..tmux.pane import capture_visible, capture_last_n

        if lines:
            output = capture_last_n(pane.pane_id, lines)
        else:
            output = capture_visible(pane.pane_id)

    # Apply filtering before returning
    return pane.handler.filter_output(output)


def get_process_info(pane: Pane) -> dict[str, Any]:
    """Get detailed process information for pane.

    Uses current scan context if available, otherwise fetches fresh.

    Args:
        pane: Target pane

    Returns:
        Dict with process details
    """
    info = {
        "pane_id": pane.pane_id,
        "session_window_pane": pane.session_window_pane,
        "pid": pane.pid,
        "shell": pane.shell.name if pane.shell else None,
        "process": pane.process.name if pane.process else None,
        "process_tree": [p.name for p in pane.process_chain],
        "handler": type(pane.handler).__name__,
    }

    # Add readiness check (three-state: True/False/None)
    is_ready, description = pane.handler.is_ready(pane)
    info["ready"] = is_ready
    info["state_description"] = description

    # Add language tag for code blocks
    info["language"] = info.get("process") or info.get("shell", "text")

    return info
