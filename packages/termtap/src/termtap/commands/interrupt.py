"""Send interrupt signal to pane.

PUBLIC API:
  - interrupt: Send Ctrl+C to pane
"""

from typing import Any

from ..app import app
from ..client import DaemonClient
from ._helpers import _require_target, build_hint


@app.command(
    display="markdown",
    fastmcp={
        "type": "tool",
        "mime_type": "text/markdown",
        "tags": {"control", "safety"},
        "description": "Send interrupt signal (Ctrl+C) to stop running process in tmux pane",
    },
)
def interrupt(state, target: str = None) -> dict[str, Any]:  # pyright: ignore[reportArgumentType]
    """Send interrupt signal (Ctrl+C) to pane.

    Args:
        state: Application state (unused).
        target: Pane target (session:window.pane).

    Returns:
        Markdown formatted result with interrupt status.
    """
    client = DaemonClient()
    resolved_target, error = _require_target(client, "interrupt", target)
    if error:
        return error
    assert resolved_target is not None

    try:
        client.interrupt(resolved_target)

        return {
            "elements": [
                {"type": "text", "content": f"Interrupt signal sent to **{resolved_target}**"},
                build_hint(resolved_target),
            ],
            "frontmatter": {
                "pane": resolved_target,
                "status": "sent",
            },
        }

    except Exception as e:
        return {
            "elements": [{"type": "text", "content": f"Error: {e}"}],
            "frontmatter": {"status": "error", "error": str(e)},
        }
