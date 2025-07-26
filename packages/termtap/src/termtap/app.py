"""termtap ReplKit2 application.

Process-native tmux session manager with MCP support. Provides command execution,
session management, and process monitoring through both REPL and MCP interfaces.
"""

from dataclasses import dataclass, field

from replkit2 import App

from .types import Target, ProcessInfo
from .config import get_target_config
from .core import execute, ExecutorState
from .tmux import list_sessions, capture_visible, capture_all, capture_last_n
from .process.detector import detect_all_processes, interrupt_process


@dataclass
class TermTapState:
    """Application state for termtap - just holds the executor."""

    executor: ExecutorState = field(default_factory=ExecutorState)


# Create the app
app = App(
    "termtap",
    TermTapState,
    uri_scheme="bash",
    fastmcp={
        "name": "termtap",
        "description": "Terminal session manager with tmux",
        "tags": {"terminal", "automation", "tmux"},
    },
)


# Register custom formatter for codeblock display
@app.formatter.register("codeblock")
def format_codeblock(data, meta, formatter):
    """Format output as markdown code block with process type."""
    if isinstance(data, dict) and "process" in data and "content" in data:
        process = data["process"]
        content = data["content"].rstrip()
        return f"```{process}\n{content}\n```"
    else:
        # Fallback for unexpected data
        return str(data)


# MCP Tool: Execute command
@app.command(
    display="codeblock",
    fastmcp={"type": "tool", "description": "Execute command in tmux session"},
)
def bash(
    state: TermTapState,
    command: str,
    target: Target = "default",
    wait: bool = True,
    timeout: float = 30.0,
) -> dict:
    """Execute command in target tmux session.

    Args:
        state: Application state.
        command: Command to execute.
        target: Target session name. Defaults to "default".
        wait: Whether to wait for completion. Defaults to True.
        timeout: Timeout in seconds. Defaults to 30.0.

    Returns:
        Dict with process and content for codeblock display.
    """
    result = execute(state.executor, command, target, wait, timeout)

    # Determine content based on status
    if result.status == "running":
        content = f"Command started in session {result.session}"
    elif result.status == "timeout":
        content = f"{result.output}\n\n[Timeout after {timeout}s]"
    else:
        content = result.output

    return {"process": result.process or "text", "content": content}


# MCP Resource: Read session output
@app.command(
    display="text",
    fastmcp={
        "type": "resource",
        "description": "Read output from tmux session",
        "uri": "bash://{target}/{lines}",
    },
)
def read(state: TermTapState, target: Target = "default", lines: int | None = None) -> str:
    """Read output from target tmux session.

    Args:
        state: Application state.
        target: Target session name. Defaults to "default".
        lines: Number of lines to read. None=visible, -1=all. Defaults to None.

    Returns:
        Session output string.
    """
    session = target

    if lines == -1:
        return capture_all(session)
    elif lines:
        return capture_last_n(session, lines)
    else:
        return capture_visible(session)


# REPL command: List sessions with process info
@app.command(display="table", headers=["Session", "Shell", "Process", "State", "Attached"], fastmcp={"enabled": False})
def ls(state: TermTapState) -> list[dict]:
    """List all tmux sessions with their current process.

    Args:
        state: Application state.

    Returns:
        List of session info with process details.
    """

    sessions = list_sessions()
    session_names = [s.name for s in sessions]

    # Get process info for all sessions in one scan
    process_infos = detect_all_processes(session_names)

    results = []
    for session in sessions:
        info = process_infos.get(session.name, ProcessInfo(shell="unknown", process=None, state="unknown"))

        results.append(
            {
                "Session": session.name,
                "Shell": info.shell,
                "Process": info.process or "-",  # Show "-" if at shell prompt
                "State": info.state,
                "Attached": "Yes" if session.attached != "0" else "No",
            }
        )

    return results


# MCP Tool: Send interrupt to session
@app.command(fastmcp={"type": "tool", "description": "Send interrupt (Ctrl+C) to a session"})
def interrupt(state: TermTapState, session: str) -> str:
    """Send interrupt (Ctrl+C) to a session.

    Args:
        state: Application state.
        session: Session name to interrupt.

    Returns:
        Status message.
    """
    success, message = interrupt_process(session)
    if success:
        return f"{session}: {message}"
    return f"Failed to interrupt {session}: {message}"


# REPL helper: Reload config
@app.command(fastmcp={"enabled": False})
def reload(state: TermTapState) -> str:
    """Reload configuration.

    Args:
        state: Application state.

    Returns:
        Reload confirmation message.
    """
    # Config is loaded on demand, so just confirm
    _ = get_target_config()  # Force reload
    return "Configuration reloaded"


if __name__ == "__main__":
    import sys

    if "--mcp" in sys.argv:
        app.mcp.run()
    else:
        app.run(title="termtap")
