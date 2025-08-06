"""Pane inspection functions - read output and get process info.

PUBLIC API:
  - read_output: Read output from pane with automatic filtering
  - get_process_info: Get process information for pane
"""

from typing import Optional, Any
from .core import Pane


def read_output(pane: Pane, lines: Optional[int] = None, mode: str = "direct") -> str:
    """Read output from pane with automatic filtering.

    Applies handler-specific filtering to remove noise and format output
    appropriately for the current process type.

    Args:
        pane: Target pane.
        lines: Number of lines to read. Defaults to visible content.
        mode: Output source - "direct" or "stream". Defaults to "direct".

    Returns:
        Filtered output string.
    """
    if mode == "stream":
        from .streaming import read_recent

        if lines:
            output = read_recent(pane, lines=lines, as_displayed=True)
        else:
            # Use reasonable default for visible content simulation
            output = read_recent(pane, lines=50, as_displayed=True)
    else:
        from ..tmux.pane import capture_visible, capture_last_n

        if lines:
            output = capture_last_n(pane.pane_id, lines)
        else:
            output = capture_visible(pane.pane_id)

    return pane.handler.filter_output(output)


def get_process_info(pane: Pane) -> dict[str, Any]:
    """Get process information for pane.

    Provides comprehensive process details including readiness state,
    process chain, and metadata for display and decision making.

    Args:
        pane: Target pane.

    Returns:
        Dict with process details and readiness state.
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

    # Include three-state readiness assessment
    is_ready, description = pane.handler.is_ready(pane)
    info["ready"] = is_ready
    info["state_description"] = description

    info["language"] = info.get("process") or info.get("shell", "text")

    return info
