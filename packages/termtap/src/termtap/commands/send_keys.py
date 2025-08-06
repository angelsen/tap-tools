"""Send raw keys command - for interacting with interactive programs."""

from typing import Any

from ..app import app
from ..pane import Pane, send_keys as pane_send_keys
from ..tmux import resolve_target_to_pane
from ..types import Target


@app.command(
    display="markdown",
    fastmcp={"type": "tool", "description": "Send raw keys to a pane"},
)
def send_keys(state, *keys: str, target: Target = "default") -> dict[str, Any]:
    """Send raw keys to target pane.

    Each key is a separate argument. Special keys like Enter, Escape, C-c are supported.

    Examples:
        send_keys("q")                      # Just q (exit less)
        send_keys("y", "Enter")             # y followed by Enter
        send_keys("Down", "Down", "Enter")  # Navigate and select
        send_keys("C-c")                    # Send Ctrl+C
        send_keys("Escape", ":q", "Enter")  # Exit vim
        send_keys("Hello", "Enter", "World") # Type text with newline
    """
    # Resolve target to single pane
    try:
        pane_id, session_window_pane = resolve_target_to_pane(target)
    except RuntimeError as e:
        return {
            "elements": [{"type": "text", "content": f"Error: {e}"}],
            "frontmatter": {"error": str(e), "status": "error"},
        }

    # Create pane and send keys
    pane = Pane(pane_id)

    # Send keys as separate arguments
    result = pane_send_keys(pane, *keys)

    # Format response
    elements = []

    if result["output"]:
        elements.append({"type": "code_block", "content": result["output"], "language": result["language"]})

    if result["status"] == "failed":
        elements.append(
            {"type": "blockquote", "content": f"Failed to send keys: {result.get('error', 'Unknown error')}"}
        )

    return {
        "elements": elements,
        "frontmatter": {
            "keys": " ".join(keys)[:40] + ("..." if len(" ".join(keys)) > 40 else ""),
            "status": result["status"],
            "pane": result["pane"],
            "elapsed": round(result["elapsed"], 2),
        },
    }
