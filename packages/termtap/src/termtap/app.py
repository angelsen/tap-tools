"""termtap ReplKit2 application - pane-first architecture.

Process-native tmux pane manager with MCP support. Everything happens
in panes; sessions are just containers for organizing panes.
"""

from dataclasses import dataclass, field

from replkit2 import App

from .types import Target, ProcessInfo, PaneRow
from .core import execute, ExecutorState
from .tmux import capture_visible, capture_all, capture_last_n
from .tmux.utils import resolve_target_to_pane, list_panes
from .process.detector import detect_process, detect_all_processes, interrupt_process


@dataclass
class TermTapState:
    """Application state for termtap pane management.

    Attributes:
        executor: ExecutorState instance managing command execution state.
    """

    executor: ExecutorState = field(default_factory=ExecutorState)


# Create the app
app = App(
    "termtap",
    TermTapState,
    uri_scheme="bash",
    fastmcp={
        "name": "termtap",
        "description": "Terminal pane manager with tmux",
        "tags": {"terminal", "automation", "tmux"},
    },
)


# Register custom formatter for codeblock display
@app.formatter.register("codeblock")  # pyright: ignore[reportAttributeAccessIssue]
def _format_codeblock(data, meta, formatter):
    """Format output as markdown code block with process type."""
    if isinstance(data, dict) and "process" in data and "content" in data:
        process = data["process"]
        content = data["content"].rstrip()
        return f"```{process}\n{content}\n```"
    else:
        return str(data)


# MCP Tool: Execute command
@app.command(
    display="codeblock",
    fastmcp={"type": "tool", "description": "Execute command in tmux pane"},
)
def bash(
    state: TermTapState,
    command: str,
    target: Target = "default",
    wait: bool = True,
    timeout: float = 30.0,
) -> dict:
    """Execute command in target pane.

    Args:
        state: Application state.
        command: Command to execute.
        target: Target pane (session:window.pane, %pane_id, or session name).
        wait: Whether to wait for completion. Defaults to True.
        timeout: Timeout in seconds. Defaults to 30.0.

    Returns:
        Dict with process and content for codeblock display.
    """
    result = execute(state.executor, command, target, wait, timeout)

    if result.status == "running":
        content = f"Command started in pane {result.session_window_pane}"
    elif result.status == "timeout":
        content = f"{result.output}\n\n[Timeout after {timeout}s]"
    else:
        content = result.output

    return {"process": result.process or "text", "content": content}


# MCP Resource: Read pane output
@app.command(
    display="codeblock",
    fastmcp={
        "type": "resource",
        "description": "Read output from tmux pane",
        "uri": "bash://{target}/{lines}",
    },
)
def read(state: TermTapState, target: Target = "default", lines: int | None = None, since_last: bool = False) -> dict:
    """Read output from target pane.

    Args:
        state: Application state.
        target: Target pane (session:window.pane, %pane_id, or session name).
        lines: Number of lines to read. None=visible, -1=all.
        since_last: Read only new content since last read() call.

    Returns:
        Dict with process and content for codeblock display.
    """
    # Resolve target to pane
    try:
        pane_id, session_window_pane = resolve_target_to_pane(target)
    except RuntimeError as e:
        return {"process": "text", "content": f"Error: {e}"}
    
    # Try to get existing stream
    stream = state.executor.stream_manager.get_stream_if_exists(pane_id)
    
    # Determine read strategy
    if stream and stream.is_running():
        # Stream exists - use it
        if since_last:
            content = stream.read_since_last()
        elif lines == -1:
            content = stream.read_all()
        elif lines:
            content = stream.read_last_lines(lines)
        else:
            # Default: read since last
            content = stream.read_since_last()
        
        # Always update last read position
        stream.mark_read("last_read")
        
    else:
        # No stream yet - fall back to direct tmux capture
        if since_last:
            # Can't do since_last without stream, get visible instead
            content = capture_visible(pane_id)
            # Now start stream for future reads
            stream = state.executor.stream_manager.get_stream(pane_id, session_window_pane)
            stream.start()
            stream.mark_read("last_read")
        elif lines == -1:
            content = capture_all(pane_id)
        elif lines:
            content = capture_last_n(pane_id, lines)
        else:
            content = capture_visible(pane_id)
    
    # Detect process for syntax highlighting
    info = detect_process(pane_id)
    process = info.process if info.process else info.shell
    
    return {"process": process, "content": content}


# REPL command: List panes with process info
@app.command(
    display="table", 
    headers=["Pane", "Shell", "Process", "State", "Attached"], 
    fastmcp={"enabled": False}
)
def ls(state: TermTapState) -> list[PaneRow]:
    """List all tmux panes with their current process.

    Args:
        state: Application state.

    Returns:
        List of pane info with process details.
    """
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


# MCP Tool: Send interrupt to pane
@app.command(fastmcp={"type": "tool", "description": "Send interrupt (Ctrl+C) to a pane"})
def interrupt(state: TermTapState, target: Target) -> str:
    """Send interrupt (Ctrl+C) to a pane.

    Args:
        state: Application state.
        target: Target pane to interrupt.

    Returns:
        Status message.
    """
    try:
        pane_id, session_window_pane = resolve_target_to_pane(target)
    except RuntimeError as e:
        return f"Failed to resolve target: {e}"
    
    success, message = interrupt_process(pane_id)
    if success:
        return f"{session_window_pane}: {message}"
    return f"Failed to interrupt {session_window_pane}: {message}"


# REPL helper: Reload config
@app.command(fastmcp={"enabled": False})
def reload(state: TermTapState) -> str:
    """Reload configuration.

    Args:
        state: Application state.

    Returns:
        Reload confirmation message.
    """
    from . import config
    config._config_manager = None
    return "Configuration reloaded"


if __name__ == "__main__":
    import sys

    if "--mcp" in sys.argv:
        app.mcp.run()
    else:
        app.run(title="termtap")