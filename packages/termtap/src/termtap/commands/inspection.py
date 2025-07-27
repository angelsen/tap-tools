"""Pane inspection and output reading."""

from ..app import app
from ..types import Target, PaneRow, ProcessInfo, ReadMode
from ..tmux import capture_visible, capture_all, capture_last_n
from ..tmux.utils import resolve_target_to_pane, list_panes
from ..process import detect_process, detect_all_processes


@app.command(
    display="codeblock",
    fastmcp={
        "type": "resource",
        "description": "Read output from tmux pane",
        "uri": "bash://{target}/{lines}",
    },
)
def read(
    state,
    target: Target = "default",
    lines: int | None = None,
    mode: ReadMode = "direct",
) -> dict:
    """Read output from target pane.
    
    Args:
        target: Target pane identifier
        lines: Number of lines (-1 for all, None for visible)
        mode: Reading mode:
            - 'direct': Direct tmux capture (default)
            - 'stream': Read new content since last read position
            - 'since_command': Not yet implemented
        
    Returns dict with content and metadata.
    """
    # Resolve target
    try:
        pane_id, session_window_pane = resolve_target_to_pane(target)
    except RuntimeError as e:
        return {
            "content": f"Error: {e}",
            "process": "text",
            "error": str(e)
        }
    
    # Stream-based modes
    if mode == "stream":
        stream = state.executor.stream_manager.get_stream(pane_id, session_window_pane)
        
        # Ensure stream exists and is running
        if not stream.stream_file.exists():
            # Lazy start the stream if not running
            if not stream.is_running():
                stream.start()
            return {
                "content": "[Stream starting - no content yet]",
                "process": "text",
                "pane_id": pane_id,
                "session_window_pane": session_window_pane,
                "mode": mode,
                "lines_read": 0,
            }
        
        content = stream.read_since_user_last()
        stream.mark_user_read()  # Update position for next read
    elif mode == "since_command":
        return {
            "content": "Error: since_command mode not yet implemented",
            "process": "text",
            "error": "since_command requires command_id parameter"
        }
    else:
        # Direct tmux capture - simple and predictable
        if lines == -1:
            content = capture_all(pane_id)
        elif lines:
            content = capture_last_n(pane_id, lines)
        else:
            content = capture_visible(pane_id)
    
    # Detect process for syntax highlighting
    info = detect_process(pane_id)
    
    return {
        # Display fields
        "content": content,
        "process": info.process or info.shell,
        
        # Metadata
        "lines_read": len(content.splitlines()) if content else 0,
        "pane_id": pane_id,
        "session_window_pane": session_window_pane,
        "mode": mode,
    }


@app.command(
    display="table",
    headers=["Pane", "Shell", "Process", "State", "Attached"],
    fastmcp={"enabled": False}  # REPL only for now
)
def ls(state) -> list[PaneRow]:
    """List all tmux panes with their current process."""
    panes = list_panes()
    pane_ids = [p.pane_id for p in panes]
    
    # Batch detect all processes in a single /proc scan
    process_infos = detect_all_processes(pane_ids)
    
    results = []
    for pane in panes:
        # Get process info from batch detection
        info = process_infos.get(
            pane.pane_id, 
            ProcessInfo(shell="unknown", process=None, state="unknown", pane_id=pane.pane_id)
        )
        
        results.append(PaneRow(
            Pane=pane.swp,
            Shell=info.shell,
            Process=info.process or "-",
            State=info.state,
            Attached="Yes" if pane.is_current else "No",
        ))
    
    return results