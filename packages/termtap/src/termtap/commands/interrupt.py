"""Interrupt command - send interrupt signal to panes."""

from typing import Any

from ..app import app
from ..pane import Pane, send_interrupt
from ..tmux import resolve_target_to_pane
from ..types import Target


@app.command(
    display="markdown",
    fastmcp={"type": "tool", "description": "Send interrupt signal to a pane"},
)
def interrupt(state, target: Target = "default") -> dict[str, Any]:
    """Send interrupt signal to target pane.

    The handler determines how to interrupt the process.
    Most processes use Ctrl+C, but some may need special handling.
    """
    # Resolve target to single pane
    try:
        pane_id, session_window_pane = resolve_target_to_pane(target)
    except RuntimeError as e:
        return {
            "elements": [{"type": "text", "content": f"Error: {e}"}],
            "frontmatter": {"error": str(e), "status": "error"},
        }

    # Create pane and send interrupt
    pane = Pane(pane_id)

    # Send interrupt - handler decides how
    result = send_interrupt(pane)

    # Format response
    elements = []

    if result["output"]:
        elements.append({"type": "code_block", "content": result["output"], "language": result["language"]})

    if result["status"] == "failed":
        elements.append({"type": "blockquote", "content": result.get("error", "Failed to send interrupt signal")})

    return {
        "elements": elements,
        "frontmatter": {
            "action": "interrupt",
            "status": result["status"],
            "pane": result["pane"],
            "elapsed": round(result["elapsed"], 2),
        },
    }
