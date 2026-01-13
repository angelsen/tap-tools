"""Execute command in tmux pane.

PUBLIC API:
  - execute: Execute command in pane via daemon
"""

from typing import Any

from ..app import app
from ..client import DaemonClient
from ._helpers import build_tips, build_hint, _require_target


@app.command(
    display="markdown",
    fastmcp={
        "type": "tool",
        "mime_type": "text/markdown",
        "tags": {"execution"},
        "description": "Execute command in tmux pane and wait for completion",
    },
)
def execute(state, command: str, target: str = None) -> dict[str, Any]:  # pyright: ignore[reportArgumentType]
    """Execute command in tmux pane.

    Args:
        state: Application state (unused).
        command: Command to execute.
        target: Pane target (session:window.pane).

    Returns:
        Markdown formatted result with output and state.
    """
    import os

    client = DaemonClient()

    # Pass client's pane (empty string if not in tmux)
    client_pane = os.environ.get("TMUX_PANE", "")

    resolved_target, error = _require_target(client, "execute", target)
    if error:
        return error
    assert resolved_target is not None

    try:
        result = client.execute(resolved_target, command, client_pane=client_pane)

        # Get status
        status = result.get("status", "unknown")

        # Build elements
        elements = [build_tips(resolved_target)]

        # Output handling based on status
        if status == "completed" and result.get("result"):
            output = result["result"].get("output", "")
            if output:
                elements.append({"type": "code_block", "content": output, "language": "text"})
            else:
                elements.append({"type": "text", "content": "(no output)"})
            elements.append(build_hint(resolved_target))
        elif status == "watching":
            elements.append({"type": "text", "content": "Command sent, watching for completion..."})
            elements.append(build_hint(resolved_target))
        elif status == "busy":
            elements.append({"type": "text", "content": "Terminal is busy"})
            elements.append(build_hint(resolved_target))
        elif status == "ready_check":
            elements.append({"type": "text", "content": "Waiting for pattern learning via Companion..."})
        else:
            elements.append({"type": "text", "content": f"Status: {status}"})

        return {
            "elements": elements,
            "frontmatter": {
                "pane": resolved_target,
                "command": command[:50] + ("..." if len(command) > 50 else ""),
                "status": status,
            },
        }

    except TimeoutError:
        return {
            "elements": [
                {
                    "type": "text",
                    "content": "Command timed out waiting for ready state. Run 'termtap companion' to respond.",
                }
            ],
            "frontmatter": {"status": "timeout", "pane": resolved_target},
        }
    except Exception as e:
        return {
            "elements": [{"type": "text", "content": f"Error: {e}"}],
            "frontmatter": {"status": "error", "error": str(e)},
        }
