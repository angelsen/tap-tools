"""List all tmux panes with their current process.

PUBLIC API:
  - ls: List all tmux panes with their current process
"""

from ..app import app
from ..pane import Pane, process_scan, get_process_info
from ..tmux import list_panes


@app.command(
    display="table",
    headers=["Pane", "Shell", "Process", "State"],
    fastmcp={
        "type": "resource",
        "mime_type": "text/plain",
        "tags": {"discovery", "inspection"},
        "description": "List all tmux panes with process information",
        "stub": {
            "response": {
                "description": "List tmux panes with optional filtering",
                "usage": ["termtap://ls - List all panes", "termtap://ls/python - Filter by 'python'"],
            }
        },
    },
)
def ls(state, filter: str = None):  # type: ignore[assignment]
    """List all tmux panes with their current process.

    Args:
        state: Application state (unused).
        filter: Filter string to search pane/process names. None shows all.

    Returns:
        Table data with pane information and process states.
    """
    tmux_panes = list_panes()

    with process_scan():
        results = []

        for tmux_pane in tmux_panes:
            pane = Pane(tmux_pane.pane_id)
            info = get_process_info(pane)

            if filter:
                searchable = f"{tmux_pane.swp} {info.get('process', '')}".lower()
                if filter.lower() not in searchable:
                    continue

            is_ready = info.get("ready")
            if is_ready is None:
                status = "unknown"
            elif is_ready:
                status = "ready"
            else:
                status = "busy"

            results.append(
                {
                    "Pane": tmux_pane.swp,
                    "Shell": info.get("shell", "-"),
                    "Process": info.get("process", "-"),
                    "State": status,
                }
            )

    return results
