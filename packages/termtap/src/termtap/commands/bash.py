"""Execute commands in tmux panes.

PUBLIC API:
  - bash: Execute command in target pane
"""

from typing import Any

from ..app import app
from ..pane import Pane, send_command
from ..tmux import resolve_or_create_target
from ..types import Target
from ..utils import truncate_command


@app.command(
    display="markdown",
    fastmcp={
        "type": "tool",
        "mime_type": "text/markdown",
        "tags": {"execution", "shell"},
        "description": "Execute shell command in tmux pane",
    },
)
def bash(
    state,
    command: str,
    target: Target = "interactive",
    wait: bool = True,
    timeout: float | None = None,
) -> dict[str, Any]:
    """Execute command in target pane.

    Args:
        state: Application state (unused).
        command: Command to execute.
        target: Target pane identifier. Defaults to "interactive".
        wait: Whether to wait for command completion. Defaults to True.
        timeout: Command timeout in seconds. Defaults to None.

    Returns:
        Markdown formatted result with command output and metadata.
    """
    # Handle interactive selection
    if target == "interactive":
        from ._popup_utils import _select_or_create_pane
        from .ls import ls

        available_panes = ls(state)
        result = _select_or_create_pane(
            available_panes, title="Execute Command", action="Choose Target Pane for Command Execution"
        )

        if not result:
            return {
                "elements": [{"type": "text", "content": "Operation cancelled"}],
                "frontmatter": {"status": "cancelled"},
            }

        pane_id, session_window_pane = result
    else:
        try:
            pane_id, session_window_pane = resolve_or_create_target(target)
        except RuntimeError as e:
            return {
                "elements": [{"type": "text", "content": f"Error: {e}"}],
                "frontmatter": {"error": str(e), "status": "error"},
            }

    pane = Pane(pane_id)
    result = send_command(pane, command, wait=wait, timeout=timeout)

    elements = []

    if result["output"]:
        elements.append({"type": "code_block", "content": result["output"], "language": result["language"]})

    if result["status"] == "timeout":
        elements.append({"type": "blockquote", "content": f"Command timed out after {result['elapsed']:.1f}s"})

    return {
        "elements": elements,
        "frontmatter": {
            "command": truncate_command(result["command"]),
            "status": result["status"],
            "pane": result["pane"],
            "elapsed": round(result["elapsed"], 2),
        },
    }
