"""Execute command in tmux pane.

PUBLIC API:
  - execute: Execute command in pane via daemon
"""

from typing import Any

from ..app import app
from ..client import DaemonClient
from ._helpers import build_tips, build_hint, error_response, _require_pane_id

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


def _output_block(pane_id: str, output: str) -> tuple[list[dict[str, str]], bool]:
    """Capped code block with truncation notice. Returns (elements, truncated)."""
    output, total = _cap_output(output)
    elements: list[dict[str, str]] = []
    if total:
        elements.append(_truncation_hint(pane_id, total))
    elements.append({"type": "code_block", "content": output, "language": "text"})
    return elements, bool(total)


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
        return error_response(str(e))

    try:
        result = client.execute(resolved_pane_id, command)

        # Get status
        status = result.get("status", "unknown")

        # Build elements
        elements = [build_tips(resolved_pane_id)]

        # Output handling based on status. client.execute polls watching/
        # ready_check to resolution, so post-call status is only ever
        # completed/busy/error/cancelled/unknown.
        if status == "completed" and result.get("result"):
            output = result["result"].get("output", "")
            if output:
                block, truncated = _output_block(resolved_pane_id, output)
                elements.extend(block)
                if not truncated:
                    elements.append(build_hint(resolved_pane_id))
            else:
                elements.append({"type": "text", "content": "(no output)"})
                elements.append(build_hint(resolved_pane_id))
        elif status == "busy":
            output = result.get("output", "")
            truncated = False
            if output:
                block, truncated = _output_block(resolved_pane_id, output)
                elements.extend(block)
            elements.append({"type": "text", "content": "Terminal is busy"})
            if not truncated:
                elements.append(build_hint(resolved_pane_id))
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

    except Exception as e:
        return error_response(str(e))
