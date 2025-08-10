"""Send interrupt signal to tmux panes.

PUBLIC API:
  - interrupt: Send interrupt signal to target pane
"""

from typing import Any

from ..app import app
from ..pane import Pane, send_interrupt
from ..tmux import resolve_target_to_pane


@app.command(
    display="markdown",
    fastmcp={
        "type": "tool",
        "mime_type": "text/markdown",
        "tags": {"control", "safety"},
        "description": "Send interrupt signal to stop running process in tmux pane",
    },
)
def interrupt(state, target: str = None) -> dict[str, Any]:  # type: ignore[assignment]
    """Send interrupt signal to target pane.

    The handler determines how to interrupt the process.
    Most processes use Ctrl+C, but some may need special handling.

    Args:
        state: Application state (unused).
        target: Target pane identifier. None for interactive selection.

    Returns:
        Markdown formatted result with interrupt status.
    """
    if target is None:
        from ._popup_utils import _select_single_pane
        from .ls import ls

        available_panes = ls(state)
        target = _select_single_pane(
            available_panes, title="Interrupt Process", action="Choose Target Pane to Interrupt"
        )

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

    result = send_interrupt(pane)

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
