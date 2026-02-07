"""Execute command in tmux pane.

PUBLIC API:
  - execute: Execute command in pane via daemon
"""

from typing import Any

from ..app import app
from ..client import DaemonClient
from ._helpers import build_tips, build_hint, _require_pane_id

_MAX_OUTPUT_LINES = 200


def _cap_output(output: str) -> tuple[str, int]:
    """Cap output to _MAX_OUTPUT_LINES, returning (output, total_lines).

    Returns total_lines=0 when not truncated.
    """
    lines = output.splitlines()
    if len(lines) <= _MAX_OUTPUT_LINES:
        return output, 0
    return "\n".join(lines[-_MAX_OUTPUT_LINES:]), len(lines)


def _truncation_hint(pane_id: str, total_lines: int) -> dict[str, str]:
    """Build truncation notice with pane() suggestion."""
    return {
        "type": "blockquote",
        "content": (
            f"Output truncated: showing last {_MAX_OUTPUT_LINES} of {total_lines} lines. "
            f'Use `mcp__termtap__pane(pane_id="{pane_id}")` for full output'
        ),
    }


@app.command(
    display="markdown",
    fastmcp={
        "type": "tool",
        "mime_type": "text/markdown",
        "tags": {"execution"},
        "description": "Execute command in tmux pane and wait for completion",
    },
)
def execute(state, command: str, pane_id: str = None) -> dict[str, Any]:  # pyright: ignore[reportArgumentType]
    """Execute command in tmux pane.

    Args:
        state: Application state (unused).
        command: Command to execute.
        pane_id: Pane ID (%format).

    Returns:
        Markdown formatted result with output and state.
    """
    client = DaemonClient()

    try:
        resolved_pane_id = _require_pane_id(client, "execute", pane_id)
    except ValueError as e:
        return {"elements": [{"type": "text", "content": str(e)}]}

    try:
        result = client.execute(resolved_pane_id, command)

        # Get status
        status = result.get("status", "unknown")

        # Build elements
        elements = [build_tips(resolved_pane_id)]

        # Output handling based on status
        if status == "completed" and result.get("result"):
            output = result["result"].get("output", "")
            if output:
                output, truncated = _cap_output(output)
                if truncated:
                    elements.append(_truncation_hint(resolved_pane_id, truncated))
                elements.append({"type": "code_block", "content": output, "language": "text"})
                if not truncated:
                    elements.append(build_hint(resolved_pane_id))
            else:
                elements.append({"type": "text", "content": "(no output)"})
                elements.append(build_hint(resolved_pane_id))
        elif status == "watching":
            elements.append({"type": "text", "content": "Command sent, watching for completion..."})
            elements.append(build_hint(resolved_pane_id))
        elif status == "busy":
            output = result.get("output", "")
            truncated = 0
            if output:
                output, truncated = _cap_output(output)
                if truncated:
                    elements.append(_truncation_hint(resolved_pane_id, truncated))
                elements.append({"type": "code_block", "content": output, "language": "text"})
            elements.append({"type": "text", "content": "Terminal is busy"})
            if not truncated:
                elements.append(build_hint(resolved_pane_id))
        elif status == "ready_check":
            elements.append({"type": "text", "content": "Waiting for pattern learning via Companion..."})
        else:
            elements.append({"type": "text", "content": f"Status: {status}"})

        return {
            "elements": elements,
            "frontmatter": {
                "pane": resolved_pane_id,
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
            "frontmatter": {"status": "timeout", "pane": resolved_pane_id},
        }
    except Exception as e:
        return {
            "elements": [{"type": "text", "content": f"Error: {e}"}],
            "frontmatter": {"status": "error", "error": str(e)},
        }
