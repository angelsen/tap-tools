"""Read output from tmux panes.

PUBLIC API:
  - read: Read output from target pane
"""

from typing import Any, Optional

from ..app import app
from ..pane import Pane, read_output, read_since_last, read_recent
from ..tmux import resolve_target_to_pane
from ..types import Target


@app.command(
    display="markdown",
    fastmcp={
        "type": "resource",
        "mime_type": "text/markdown",
        "tags": {"inspection", "output"},
        "description": "Read output from tmux pane with metadata",
        "stub": {
            "response": {
                "example": "termtap://read/test-session",
                "description": "Replace 'test-session' with any pane target",
                "usage": "Use termtap://ls to find available pane targets",
            }
        },
    },
)
def read(
    state,
    target: Target = "default",
    lines: Optional[int] = None,
    since_last: bool = False,
    mode: str = "direct",
) -> dict[str, Any]:
    """Read output from target pane.

    Args:
        state: Application state (unused).
        target: Pane to read from. Defaults to "default".
        lines: Number of lines to read. Defaults to None.
        since_last: Read only new output since last read. Defaults to False.
        mode: Read mode - "direct" or "stream". Defaults to "direct".

    Returns:
        Markdown formatted result with pane output.
    """
    if since_last and mode != "stream":
        return {
            "elements": [{"type": "text", "content": "Error: since_last requires mode='stream'"}],
            "frontmatter": {"error": "Invalid parameters", "status": "error"},
        }

    try:
        pane_id, session_window_pane = resolve_target_to_pane(target)
    except RuntimeError as e:
        return {
            "elements": [{"type": "text", "content": f"Error: {e}"}],
            "frontmatter": {"error": str(e), "status": "error"},
        }

    pane = Pane(pane_id)

    if mode == "stream":
        if since_last:
            output = read_since_last(pane)
        else:
            output = read_recent(pane, lines=lines) if lines else read_recent(pane)
    else:  # direct
        output = read_output(pane, lines=lines, mode="direct")

    from ..pane import get_process_info

    info = get_process_info(pane)

    elements = [
        {
            "type": "code_block",
            "content": output or "[No output]",
            "language": info["language"],
        }
    ]

    return {
        "elements": elements,
        "frontmatter": {
            "target": target,
            "pane": session_window_pane,
            "mode": mode,
            "lines": lines,
            "since_last": since_last,
        },
    }
