"""Execute commands in tmux panes."""

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
    """Execute command in target pane."""
    # Resolve target to pane
    try:
        pane_id, session_window_pane = resolve_or_create_target(target)
    except RuntimeError as e:
        return {
            "elements": [{"type": "text", "content": f"Error: {e}"}],
            "frontmatter": {"error": str(e), "status": "error"},
        }
    
    # Create pane and execute command
    pane = Pane(pane_id)
    result = send_command(pane, command, wait=wait, timeout=timeout)
    
    # Format response
    elements = []
    
    if result["output"]:
        # Use language from result metadata (no additional scan needed!)
        elements.append({
            "type": "code_block",
            "content": result["output"],
            "language": result["language"]
        })
    
    if result["status"] == "timeout":
        elements.append({
            "type": "blockquote",
            "content": f"Command timed out after {result['elapsed']:.1f}s"
        })
    
    return {
        "elements": elements,
        "frontmatter": {
            "command": command.replace("\n", "\\n")[:40],
            "status": result["status"],
            "pane": result["pane"],
            "elapsed": round(result["elapsed"], 2),
        }
    }