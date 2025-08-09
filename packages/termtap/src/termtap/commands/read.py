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
                "description": "Read output from tmux pane with optional parameters",
                "usage": [
                    "termtap://read - Interactive pane selection",
                    "termtap://read/session1 - Read from specific pane",
                    "termtap://read/session1/100 - Read 100 lines",
                    "termtap://read/session1/100/true/stream - All parameters",
                ],
                "discovery": "Use termtap://ls to find available pane targets",
            }
        },
    },
)
def read(
    state,
    target: Target = "interactive",
    lines: Optional[int] = None,
    since_last: bool = False,
    mode: str = "direct",
) -> dict[str, Any]:
    """Read output from target pane.

    Args:
        state: Application state (unused).
        target: Pane to read from. Defaults to "interactive" for interactive selection.
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

    if target == "interactive":
        from ._popup_utils import select_single_pane
        from .ls import ls
        
        available_panes = ls(state)
        if not available_panes:
            return {
                "elements": [{"type": "text", "content": "Error: No panes available"}],
                "frontmatter": {"error": "No panes available", "status": "error"},
            }
        
        selected_pane_id = select_single_pane(
            available_panes,
            title="Read Output",
            action="Select Pane to Read From"
        )
        
        if not selected_pane_id:
            return {
                "elements": [{"type": "text", "content": "Error: No pane selected"}],
                "frontmatter": {"error": "No pane selected", "status": "error"},
            }
        
        session_window_pane = selected_pane_id
        pane_id = selected_pane_id
        
        from ..tmux import list_panes as tmux_list_panes
        for pane_info in tmux_list_panes():
            if pane_info.swp == selected_pane_id:
                pane_id = pane_info.pane_id
                break
    else:
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
