"""List command - show all tmux panes."""

from typing import cast, Optional
from ..app import app
from ..types import PaneRow, ProcessInfo
from ..tmux import list_panes
from ..process import detect_all_processes
from ..errors import table_error_response
import logging

logger = logging.getLogger(__name__)


@app.command(
    display="table",
    headers=["Pane", "Shell", "Process", "State", "Attached"],
    fastmcp={"enabled": False},  # REPL only for now
)
def ls(state, filter: Optional[str] = None) -> list[PaneRow]:
    """List all tmux panes with their current process.

    Args:
        filter: Optional text to filter (searches in pane name and process)
    """
    try:
        panes = list_panes()
        pane_ids = [p.pane_id for p in panes]
    except Exception as e:
        return cast(list[PaneRow], table_error_response(f"Failed to list panes: {e}"))

    # Batch detect all processes
    try:
        process_infos = detect_all_processes(pane_ids)
    except Exception as e:
        # If batch detection fails, log it but continue with empty infos
        logger.warning(f"Batch process detection failed: {e}")
        process_infos = {}

    results = []
    for pane in panes:
        try:
            # Get process info or use defaults
            info = process_infos.get(
                pane.pane_id, ProcessInfo(shell="unknown", process=None, state="unknown", pane_id=pane.pane_id)
            )

            # Skip panes that had detection errors
            if info.shell == "error":
                continue

            # Apply filter if provided
            if filter:
                # Simple fuzzy search in pane name and process
                searchable = f"{pane.swp} {info.process or ''}".lower()
                if filter.lower() not in searchable:
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
        except Exception as e:
            # Log individual pane errors but continue
            logger.warning(f"Failed to process pane {pane.pane_id}: {e}")
            continue

    return results
