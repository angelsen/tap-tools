"""Send interrupt signal to pane.

PUBLIC API:
  - interrupt: Send Ctrl+C to pane
"""

from typing import Any

from ..app import app
from ..client import DaemonClient
from ._helpers import _require_pane_id, build_hint


@app.command(
    display="markdown",
    fastmcp={
        "type": "tool",
        "mime_type": "text/markdown",
        "tags": {"control", "safety"},
        "description": "Send interrupt signal (Ctrl+C) to stop running process in tmux pane",
    },
)
def interrupt(state, pane_id: str = None) -> dict[str, Any]:  # pyright: ignore[reportArgumentType]
    """Send interrupt signal (Ctrl+C) to pane.

    Args:
        state: Application state (unused).
        pane_id: Pane ID (%format).

    Returns:
        Markdown formatted result with interrupt status.
    """
    client = DaemonClient()

    try:
        resolved_pane_id = _require_pane_id(client, "interrupt", pane_id)
    except ValueError as e:
        return {"elements": [{"type": "text", "content": str(e)}]}

    try:
        client.interrupt(resolved_pane_id)

        return {
            "elements": [
                {"type": "text", "content": f"Interrupt signal sent to **{resolved_pane_id}**"},
                build_hint(resolved_pane_id),
            ],
            "frontmatter": {
                "pane": resolved_pane_id,
                "status": "sent",
            },
        }

    except Exception as e:
        return {
            "elements": [{"type": "text", "content": f"Error: {e}"}],
            "frontmatter": {"status": "error", "error": str(e)},
        }
