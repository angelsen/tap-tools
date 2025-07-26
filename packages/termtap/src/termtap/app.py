"""termtap ReplKit2 application.

Process-native tmux session manager with MCP support. Provides command execution,
session management, and process monitoring through both REPL and MCP interfaces.
"""

from dataclasses import dataclass, field

from replkit2 import App

from .types import Target
from .config import get_target_config
from .core import execute, ExecutorState, send_interrupt
from .tmux import list_sessions, capture_visible, capture_all, capture_last_n
from .process import get_process_info


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


# MCP Tool: Execute command
@app.command(
    display="text",
    fastmcp={"type": "tool", "description": "Execute command in tmux session"},
)
def bash(
    state: TermTapState,
    command: str,
    target: Target = "default",
    wait: bool = True,
    timeout: float = 30.0,
) -> str:
    """Execute command in target tmux session.

    Args:
        state: Application state.
        command: Command to execute.
        target: Target session name. Defaults to "default".
        wait: Whether to wait for completion. Defaults to True.
        timeout: Timeout in seconds. Defaults to 30.0.

    Returns:
        Command output or status message.
    """
    result = execute(state.executor, command, target, wait, timeout)

    if result.status == "running":
        return f"Command started in session {result.session}"
    elif result.status == "timeout":
        return f"{result.output}\n\n[Timeout after {timeout}s]"
    else:
        return result.output


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
@app.command(display="table", headers=["Session", "Process", "State", "Attached"], fastmcp={"enabled": False})
def ls(state: TermTapState) -> list[dict]:
    """List all tmux sessions with their current process.

    Args:
        state: Application state.

    Returns:
        List of session info with process details.
    """
    from .process.tree import get_all_processes, build_tree_from_processes
    from .process.detector import _find_active_process
    from .tmux.utils import get_pane_pid
    from .config import get_target_config

    sessions = list_sessions()
    results = []

    # Scan /proc once for all processes
    all_processes = get_all_processes()

    # Get config once
    config = get_target_config()

    for session in sessions:
        try:
            # Get pane PID
            pid = get_pane_pid(session.name)

            # Build tree from cached process data
            tree = build_tree_from_processes(all_processes, pid)

            if not tree:
                process_display = "unknown"
                state_display = "error"
            else:
                # Extract chain from tree
                chain = []
                current = tree
                visited = set()
                while current and current.pid not in visited:
                    visited.add(current.pid)
                    chain.append(current)
                    if current.children:
                        current = current.children[0]
                    else:
                        break

                # Find active process
                active = _find_active_process(chain, config.skip_processes)

                if active:
                    process_display = active.name
                    state_display = "ready" if active.is_sleeping else "running"
                else:
                    process_display = "none"
                    state_display = "empty"

        except Exception:
            process_display = "unknown"
            state_display = "error"

        results.append(
            {
                "Session": session.name,
                "Process": process_display,
                "State": state_display,
                "Attached": "Yes" if session.attached != "0" else "No",
            }
        )

    return results


# REPL command: Show active (working) processes
@app.command(display="table", headers=["Session", "Process", "PID"], fastmcp={"enabled": False})
def active(state: TermTapState) -> list[dict]:
    """Show sessions with processes doing work (not waiting for input).

    Args:
        state: Application state.

    Returns:
        List of active processes.
    """
    sessions = list_sessions()
    results = []

    for session in sessions:
        info = get_process_info(session.name)

        # Check if process is actively running
        if info.get("active") and not info["active"]["is_sleeping"]:
            active = info["active"]
            results.append({"Session": session.name, "Process": active["name"], "PID": str(active["pid"])})

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
    if send_interrupt(session):
        return f"Sent interrupt to {session}"
    return f"Failed to interrupt {session}"


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
