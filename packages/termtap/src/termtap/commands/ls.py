"""List all tmux panes.

PUBLIC API:
  - ls: List all tmux panes
"""

from ..app import app
from ..client import DaemonClient


@app.command(
    display="table",
    headers=["Pane", "Session", "Window", "PID"],
    fastmcp={
        "type": "resource",
        "mime_type": "text/plain",
        "tags": {"discovery", "inspection"},
        "description": "List all tmux panes",
        "stub": {
            "response": {
                "description": "List tmux panes with optional filtering",
                "usage": [
                    "termtap://ls - List all panes",
                    "termtap://ls/python - Filter by 'python'",
                ],
            }
        },
    },
)
def ls(state, filter: str = None):  # pyright: ignore[reportArgumentType]
    """List all tmux panes.

    Args:
        state: Application state (unused).
        filter: Filter string to search pane names. None shows all.

    Returns:
        Table data with pane information.
    """
    client = DaemonClient(auto_start=False)

    try:
        result = client.ls()
        panes = result.get("panes", [])
    except Exception:
        # Fallback to direct tmux if daemon not running
        from ..tmux.ops import list_panes

        panes = [
            {
                "swp": p.swp,
                "session": p.session,
                "window_index": p.window_index,
                "pane_pid": p.pane_pid,
            }
            for p in list_panes()
        ]

    results = []
    for pane in panes:
        swp = pane.get("swp", "")

        if filter:
            if filter.lower() not in swp.lower():
                continue

        results.append(
            {
                "Pane": swp,
                "Session": pane.get("session", "-"),
                "Window": pane.get("window_index", 0),
                "PID": pane.get("pane_pid", "-"),
            }
        )

    return results
