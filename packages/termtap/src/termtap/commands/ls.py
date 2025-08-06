"""List command - show all tmux panes."""

from typing import Optional

from ..app import app
from ..pane import Pane, process_scan, get_process_info
from ..tmux import list_panes


@app.command(
    display="table",
    headers=["Pane", "Shell", "Process", "State"],
)
def ls(state, filter: Optional[str] = None):
    """List all tmux panes with their current process."""
    tmux_panes = list_panes()
    
    # Single scan for all panes
    with process_scan():
        results = []
        
        for tmux_pane in tmux_panes:
            # Create pane - will use scan context
            pane = Pane(tmux_pane.pane_id)
            info = get_process_info(pane)
            
            # Apply filter if provided
            if filter:
                searchable = f"{tmux_pane.swp} {info.get('process', '')}".lower()
                if filter.lower() not in searchable:
                    continue
            
            # Map three-state boolean to status
            is_ready = info.get("ready")
            if is_ready is None:
                status = "unknown"
            elif is_ready:
                status = "ready"
            else:
                status = "busy"
            
            results.append({
                "Pane": tmux_pane.swp,
                "Shell": info.get("shell", "-"),
                "Process": info.get("process", "-"),
                "State": status,
            })
    
    return results