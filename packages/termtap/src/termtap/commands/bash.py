"""Execute commands in tmux panes.

PUBLIC API:
  - bash: Execute command in target pane
"""

from typing import Any

from ..app import app
from ..pane import Pane, send_command
from ..tmux import resolve_or_create_target
from ..types import Target


@app.command(
    display="markdown",
    fastmcp={"type": "tool", "description": "Execute command in tmux pane"},
)
def bash(
    state,
    command: str,
    target: Target = "default",
    wait: bool = True,
    timeout: float | None = None,
) -> dict[str, Any]:
    """Execute command in target pane.

    Args:
        state: Application state (unused).
        command: Command to execute.
        target: Target pane identifier. Defaults to "default".
        wait: Whether to wait for command completion. Defaults to True.
        timeout: Command timeout in seconds. Defaults to None.

    Returns:
        Markdown formatted result with command output and metadata.
    """
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
        # Use language from result metadata
        elements.append({"type": "code_block", "content": result["output"], "language": result["language"]})

    if result["status"] == "timeout":
        elements.append({"type": "blockquote", "content": f"Command timed out after {result['elapsed']:.1f}s"})

    return {
        "elements": elements,
        "frontmatter": {
            "command": command.replace("\n", "\\n")[:40],
            "status": result["status"],
            "pane": result["pane"],
            "elapsed": round(result["elapsed"], 2),
        },
    }
