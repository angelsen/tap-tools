"""Read output from tmux panes.

PUBLIC API:
  - read: Read output from target pane
"""

from typing import Any, Optional, Union, List

from ..app import app
from ..pane import Pane, read_output, read_since_last, read_recent
from ..tmux import resolve_targets_to_panes
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
    target: Union[Target, List[Target]] = "interactive",
    lines: Optional[int] = None,
    since_last: bool = False,
    mode: str = "direct",
) -> dict[str, Any]:
    """Read output from one or more target panes.

    Args:
        state: Application state (unused).
        target: Single target, list of targets, or "interactive" for selection.
                Examples: "demo", ["demo.frontend", "test:0"], "interactive"
        lines: Number of lines to read. Defaults to None.
        since_last: Read only new output since last read. Defaults to False.
        mode: Read mode - "direct" or "stream". Defaults to "direct".

    Returns:
        Markdown formatted result with pane output(s).
    """
    if since_last and mode != "stream":
        return {
            "elements": [{"type": "text", "content": "Error: since_last requires mode='stream'"}],
            "frontmatter": {"error": "Invalid parameters", "status": "error"},
        }

    # Handle interactive selection
    if target == "interactive":
        from ._popup_utils import _select_multiple_panes
        from .ls import ls

        available_panes = ls(state)
        if not available_panes:
            return {
                "elements": [{"type": "text", "content": "Error: No panes available"}],
                "frontmatter": {"error": "No panes available", "status": "error"},
            }

        selected_pane_ids = _select_multiple_panes(
            available_panes, title="Read Output", action="Select Panes to Read From (space to select, enter to confirm)"
        )

        if not selected_pane_ids:
            return {
                "elements": [{"type": "text", "content": "Error: No panes selected"}],
                "frontmatter": {"error": "No panes selected", "status": "error"},
            }

        targets_to_resolve = selected_pane_ids
    else:
        targets_to_resolve = target

    try:
        panes_to_read = resolve_targets_to_panes(targets_to_resolve)
    except RuntimeError as e:
        return {
            "elements": [{"type": "text", "content": f"Error: {e}"}],
            "frontmatter": {"error": str(e), "status": "error"},
        }

    if not panes_to_read:
        return {
            "elements": [{"type": "text", "content": "Error: No panes found for target(s)"}],
            "frontmatter": {"error": "No panes found", "status": "error"},
        }

    elements = []
    pane_info_list = []

    for pane_id, session_window_pane in panes_to_read:
        pane = Pane(pane_id)

        if mode == "stream":
            if since_last:
                output = read_since_last(pane)
            else:
                output = read_recent(pane, lines=lines) if lines else read_recent(pane)
        else:
            output = read_output(pane, lines=lines, mode="direct")

        from ..pane import get_process_info

        info = get_process_info(pane)

        if len(panes_to_read) > 1:
            elements.append({"type": "heading", "content": f"{session_window_pane}", "level": 3})

        elements.append(
            {
                "type": "code_block",
                "content": output or "[No output]",
                "language": info.get("language", "text"),
            }
        )

        pane_info_list.append(session_window_pane)

    frontmatter = {
        "target": target if target != "interactive" else "interactive selection",
        "panes": pane_info_list if len(pane_info_list) > 1 else pane_info_list[0],
        "mode": mode,
        "lines": lines,
        "since_last": since_last,
    }

    return {
        "elements": elements,
        "frontmatter": frontmatter,
    }
