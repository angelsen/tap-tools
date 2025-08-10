"""Send raw keys to tmux panes for interactive programs.

PUBLIC API:
  - send_keys: Send raw keys to target pane
"""

from typing import Any

from ..app import app
from ..pane import Pane, send_keys as pane_send_keys
from ..tmux import resolve_target_to_pane


@app.command(
    display="markdown",
    fastmcp={
        "type": "tool",
        "mime_type": "text/markdown",
        "tags": {"input", "control"},
        "description": "Send raw keystrokes to tmux pane (for special keys like Ctrl+C, arrows, Escape). Use execute for commands",
    },
)
def send_keys(state, keys: str, target: str = None) -> dict[str, Any]:  # type: ignore[assignment]
    """Send raw keys to target pane.

    Space-separated keys string. Special keys like Enter, Escape, C-c are supported.

    Args:
        state: Application state (unused).
        keys: Space-separated keys to send (e.g., "q", "Down Down Enter", "C-c").
        target: Target pane identifier. None for interactive selection.

    Returns:
        Markdown formatted result with key sending status.

    Examples:
        send_keys("q")                      # Just q (exit less)
        send_keys("y Enter")                # y followed by Enter
        send_keys("Down Down Enter")        # Navigate and select
        send_keys("C-c")                    # Send Ctrl+C
        send_keys("Escape :q Enter")        # Exit vim
        send_keys("Hello Enter World")      # Type text with newline
    """
    if target is None:
        from ._popup_utils import _select_single_pane
        from .ls import ls

        available_panes = ls(state)
        target = _select_single_pane(available_panes, title="Send Keys", action="Choose Target Pane for Key Input")

        if not target:
            return {
                "elements": [{"type": "text", "content": "Operation cancelled"}],
                "frontmatter": {"status": "cancelled"},
            }

    try:
        pane_id, session_window_pane = resolve_target_to_pane(target)
    except RuntimeError as e:
        return {
            "elements": [{"type": "text", "content": f"Error: {e}"}],
            "frontmatter": {"error": str(e), "status": "error"},
        }

    pane = Pane(pane_id)

    result = pane_send_keys(pane, keys)

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
            "keys": keys[:40] + ("..." if len(keys) > 40 else ""),
            "status": result["status"],
            "pane": result["pane"],
            "elapsed": round(result["elapsed"], 2),
        },
    }
