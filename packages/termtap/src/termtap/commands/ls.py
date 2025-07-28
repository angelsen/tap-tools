"""List command - show all tmux panes."""

from ..app import app
from ..types import PaneRow, ProcessInfo
from ..tmux.utils import list_panes
from ..process import detect_all_processes


@app.command(
    display="table",
    headers=["Pane", "Shell", "Process", "State", "Attached"],
    fastmcp={"enabled": False},  # REPL only for now
)
def ls(state) -> list[PaneRow]:
    """List all tmux panes with their current process."""
    panes = list_panes()
    pane_ids = [p.pane_id for p in panes]

    # Batch detect all processes
    try:
        process_infos = detect_all_processes(pane_ids)
    except Exception as e:
        # If batch detection fails, create empty infos
        print(f"Warning: Batch process detection failed: {e}")
        process_infos = {}

    results = []
    for pane in panes:
        # Get process info or use defaults
        info = process_infos.get(
            pane.pane_id, ProcessInfo(shell="unknown", process=None, state="unknown", pane_id=pane.pane_id)
        )

        # Skip panes that had detection errors
        if info.shell == "error":
            continue

        results.append(
            PaneRow(
                Pane=pane.swp,
                Shell=info.shell,
                Process=info.process or "-",
                State=info.state,
                Attached="Yes" if pane.is_current else "No",
            )
        )

    return results
