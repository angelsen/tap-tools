"""Interrupt command - send Ctrl+C to panes."""

from ..app import app
from ..types import Target
from ..tmux.utils import resolve_target_to_pane
from ..process import interrupt_process


@app.command(fastmcp={"type": "tool", "description": "Send interrupt (Ctrl+C) to a pane"})
def interrupt(state, target: Target) -> str:
    """Send interrupt (Ctrl+C) to a pane."""
    try:
        pane_id, session_window_pane = resolve_target_to_pane(target)
    except RuntimeError as e:
        return f"Failed to resolve target: {e}"

    success, message = interrupt_process(pane_id)
    if success:
        return f"{session_window_pane}: {message}"
    return f"Failed to interrupt {session_window_pane}: {message}"
