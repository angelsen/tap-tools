"""Command execution in tmux panes."""

from ..app import app
from ..types import Target
from ..core import execute
from ..tmux.utils import resolve_target_to_pane
from ..process import interrupt_process


@app.command(
    display="codeblock",
    fastmcp={"type": "tool", "description": "Execute command in tmux pane"},
)
def bash(
    state,
    command: str,
    target: Target = "default",
    wait: bool = True,
    timeout: float = 30.0,
) -> dict:
    """Execute command in target pane.
    
    Returns rich data dict:
    - Display fields: content, process
    - Metadata: command_id, pane_id, session_window_pane, status, duration
    """
    result = execute(state.executor, command, target, wait, timeout)
    
    # Build display content
    if result.status == "running":
        content = f"Command started in pane {result.session_window_pane}"
    elif result.status == "timeout":
        content = f"{result.output}\n\n[Timeout after {timeout}s]"
    else:
        content = result.output
    
    # Return rich data structure
    return {
        # Display fields (used by formatter)
        "content": content,
        "process": result.process or "text",
        
        # Metadata fields (preserved for programmatic use)
        "command_id": result.command_id,
        "command": command,
        "pane_id": result.pane_id,
        "session_window_pane": result.session_window_pane,
        "status": result.status,
        "duration": result.duration,
        "target": target,  # Original target for convenience
    }


@app.command(
    fastmcp={"type": "tool", "description": "Send interrupt (Ctrl+C) to a pane"}
)
def interrupt(state, target: Target) -> str:
    """Send interrupt (Ctrl+C) to a pane."""
    try:
        pane_id, session_window_pane = resolve_target_to_pane(target)
    except RuntimeError as e:
        return f"Failed to resolve target: {e}"
    
    success, message = interrupt_process(pane_id)
    if success:
        return f"{session_window_pane}: {message}"
    return f"Failed to interrupt {session_window_pane}: {message}"