"""Pane inspection functions - read output and get process info.

PUBLIC API:
  - read_output: Read output from pane with automatic filtering
  - get_process_info: Get process information for pane
"""

from typing import Optional, Any
from .core import Pane


def read_output(pane: Pane, lines: Optional[int] = None, mode: str = "direct") -> str:
    """Read output from pane with automatic filtering.

    Uses the unified capture_output method with appropriate parameters
    based on mode and line requirements.

    Args:
        pane: Target pane.
        lines: Number of lines to read. Defaults to visible content.
        mode: Output source - "direct" or "stream". Defaults to "direct".

    Returns:
        Filtered output string using handler's capture_output method.
    """
    if mode == "stream":
        # Use streaming capture method
        if lines and lines <= 50:
            # For small line counts, use last_n which is more precise
            return pane.handler.capture_output(pane, method="last_n")
        else:
            # Use streaming method for larger requests or default
            return pane.handler.capture_output(pane, method="stream")
    else:
        # Direct mode
        if lines:
            # Specific line count requested
            return pane.handler.capture_output(pane, method="last_n")
        else:
            # Default to visible content
            return pane.handler.capture_output(pane, method="visible")


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
