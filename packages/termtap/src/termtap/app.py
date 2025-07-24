"""termtap ReplKit2 application.

Process-native tmux session manager with MCP support. Provides command execution,
session management, and process monitoring through both REPL and MCP interfaces.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List

from replkit2 import App

from .config import load_config
from .core import execute, get_result, ExecutorState, abort_command
from .hover import should_hover, check_tmux_hover_env, pattern_hover_callback, show_hover
from .tmux import list_sessions, SessionInfo, kill_session, capture_visible

_LOGGING_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Set up logging
logging.basicConfig(level=logging.INFO, format=_LOGGING_FORMAT)
logger = logging.getLogger(__name__)


@dataclass
class TermTapState:
    """Application state for termtap.

    Manages executor state and configuration for tmux session operations.

    Attributes:
        executor: Command execution state tracking.
        config: Configuration dictionary for session targets.
    """

    executor: ExecutorState = field(default_factory=ExecutorState)
    config: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Load configuration on initialization."""
        self.config = {k: v.__dict__ for k, v in load_config().items()}

    @property
    def sessions(self) -> list[SessionInfo]:
        """Get all tmux sessions.

        Returns:
            List of SessionInfo objects for active sessions.
        """
        return list_sessions()

    @property
    def active_commands(self) -> dict:
        """Get active commands.

        Returns:
            Dictionary mapping command IDs to command info.
        """
        return self.executor.active_commands


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
    display="text",  # Changed from "box" to "text" to avoid formatting issues
    fastmcp={"type": "tool", "description": "Execute command in tmux session"},
)
def bash(
    state: TermTapState,
    command: str,
    target: str = "default",
    wait: bool = True,
    timeout: float = 30.0,
    hover: Optional[bool] = None,
) -> str:
    """Execute command in target tmux session.

    Args:
        state: Application state.
        command: Command to execute.
        target: Target session name. Defaults to "default".
        wait: Whether to wait for completion. Defaults to True.
        timeout: Timeout in seconds. Defaults to 30.0.
        hover: Enable hover dialog. Defaults to None (auto-detect).

    Returns:
        Command output or status message.
    """
    config = state.config.get(target, state.config["default"])

    if hover is None:
        hover = check_tmux_hover_env() or should_hover(command, config)

    if hover:
        logger.info(f"Pre-execution hover triggered for command: {command[:50]}...")
        session = target
        result = show_hover(session=session, command=command, mode="before")

        if result.action == "cancel":
            logger.info("User cancelled command via hover")
            return "Cancelled"
        elif result.action == "edit" and result.message:
            logger.info(f"User edited command: {result.message[:50]}...")
            command = result.message
        elif result.action == "join":
            import os

            os.system(f"tmux attach -t {session}")
            return "Joined session"

    hover_callback = None
    if config.get("hover_patterns"):
        logger.info(f"Pattern hover enabled with patterns: {config.get('hover_patterns')}")

        def callback(pattern, output):
            logger.info(f"Pattern callback triggered: pattern='{pattern}'")
            return pattern_hover_callback(pattern, output, target, command)

        hover_callback = callback

    result = execute(
        state.executor, command=command, target=target, wait=wait, timeout=timeout, hover_check=hover_callback
    )

    if result.status == "running":
        return f"Command started (ID: {result.cmd_id})\nUse 'status {result.cmd_id}' to check progress"
    elif result.status == "timeout":
        return f"{result.output}\n\n[Timeout after {timeout}s - ID: {result.cmd_id}]"
    elif result.status == "aborted":
        return f"{result.output}\n\n[Aborted]"
    else:
        return result.output


# MCP Resource: Read session output
@app.command(
    display="tree",
    fastmcp={
        "type": "resource",
        "description": "Read output from tmux session with process info",
        "uri": "bash://{target}/{lines}",
    },
)
def read(state: TermTapState, target: str = "default", lines: Optional[int] = None, include_state: bool = False) -> Any:
    """Read output from target tmux session.

    Args:
        state: Application state.
        target: Target session name. Defaults to "default".
        lines: Number of lines to read. Defaults to None (visible).
        include_state: Include process state info. Defaults to False.

    Returns:
        Session output string or dict with process info.
    """
    from .tmux import capture_last_n, capture_all
    from .tmux.stream import _get_pane_for_session
    from .process import get_process_context

    session = target

    pane_id = _get_pane_for_session(session)

    if lines == -1:
        output = capture_all(pane_id)
    elif lines:
        output = capture_last_n(pane_id, lines)
    else:
        output = capture_visible(pane_id)

    if not include_state:
        return output

    from .tmux.utils import _run_tmux

    code, stdout, _ = _run_tmux(["display", "-p", "-t", pane_id, "#{pane_pid}"])

    if code == 0 and stdout.strip():
        try:
            pid = int(stdout.strip())
            context = get_process_context(pid)

            return {
                "output": output,
                "session": session,
                "process": {
                    "shell": context.shell_type if context else "unknown",
                    "current": context.current_program if context else "unknown",
                    "ready": context and context.process_tree[-1].is_sleeping,
                    "tree": [p.name for p in context.process_tree] if context else [],
                }
                if context
                else None,
            }
        except ValueError:
            pass

    return {"output": output, "session": session}


# REPL command: List sessions
@app.command(display="table", headers=["Session", "Created", "Attached"], fastmcp={"enabled": False})
def ls(state: TermTapState) -> List[dict]:
    """List all tmux sessions.

    Args:
        state: Application state.

    Returns:
        List of session dictionaries with name, created, and attached status.
    """
    sessions = []
    for s in state.sessions:
        sessions.append({"Session": s.name, "Created": s.created, "Attached": "Yes" if s.attached != "0" else "No"})
    return sessions


# REPL command: Join session
@app.command(fastmcp={"enabled": False})
def join(state: TermTapState, session: str) -> str:
    """Join a tmux session.

    Args:
        state: Application state.
        session: Session name to join.

    Returns:
        Success message.
    """
    import os

    os.system(f"tmux attach -t {session}")
    return f"Joined {session}"


# REPL command: Kill session
@app.command(fastmcp={"enabled": False})
def kill(state: TermTapState, session: str) -> str:
    """Kill a tmux session.

    Args:
        state: Application state.
        session: Session name to kill.

    Returns:
        Success or failure message.
    """
    if kill_session(session):
        return f"Killed {session}"
    else:
        return f"Failed to kill {session}"


# MCP Tool: Get command status
@app.command(display="tree", fastmcp={"type": "tool", "description": "Get status of running command with process info"})
def status(state: TermTapState, cmd_id: str) -> dict:
    """Get status of a running command.

    Args:
        state: Application state.
        cmd_id: Command ID to check.

    Returns:
        Dictionary with command status and process info.
    """
    result = get_result(state.executor, cmd_id)

    process_info = None
    if result.status == "running" and cmd_id in state.executor.active_commands:
        cmd_info = state.executor.active_commands[cmd_id]
        pane_id = cmd_info.get("pane_id")

        if pane_id:
            from .tmux.utils import _run_tmux
            from .process import get_process_context

            code, stdout, _ = _run_tmux(["display", "-p", "-t", pane_id, "#{pane_pid}"])
            if code == 0 and stdout.strip():
                try:
                    pid = int(stdout.strip())
                    context = get_process_context(pid)
                    if context:
                        process_info = {
                            "Shell": context.shell_type,
                            "Current": context.current_program,
                            "Ready": context.process_tree[-1].is_sleeping,
                            "Tree": " → ".join(p.name for p in context.process_tree),
                        }
                except ValueError:
                    pass

    status_dict = {
        "Command": {
            "ID": cmd_id,
            "Status": result.status,
            "Session": result.session,
            "Metrics": {
                "Elapsed": f"{result.elapsed:.1f}s" if result.elapsed else "N/A",
                "Output Lines": len(result.output.split("\n")),
            },
        }
    }

    if process_info:
        status_dict["Process"] = process_info

    return status_dict


# MCP Tool: Abort command
@app.command(fastmcp={"type": "tool", "description": "Abort a running command"})
def abort(state: TermTapState, cmd_id: str) -> str:
    """Abort a running command.

    Args:
        state: Application state.
        cmd_id: Command ID to abort.

    Returns:
        Abort confirmation message.
    """

    result = abort_command(state.executor, cmd_id)

    if result.status == "not_found":
        return f"Command {cmd_id} not found"
    else:
        return f"Aborted command in {result.session}"


# REPL command: Show active commands
@app.command(display="table", headers=["ID", "Command", "Session", "Elapsed"], fastmcp={"enabled": False})
def active(state: TermTapState) -> List[dict]:
    """Show active commands.

    Args:
        state: Application state.

    Returns:
        List of active command dictionaries.
    """
    import time

    commands = []
    for cmd_id, info in state.active_commands.items():
        elapsed = time.time() - info["started"]
        commands.append(
            {
                "ID": cmd_id[:8],
                "Command": info["command"][:40] + ("..." if len(info["command"]) > 40 else ""),
                "Session": info["session"],
                "Elapsed": f"{elapsed:.1f}s",
            }
        )
    return commands


# REPL command: Reload config
@app.command(fastmcp={"enabled": False})
def reload(state: TermTapState) -> str:
    """Reload configuration.

    Args:
        state: Application state.

    Returns:
        Reload confirmation message.
    """
    state.config = {k: v.__dict__ for k, v in load_config().items()}
    return f"Reloaded config with {len(state.config)} targets"


# Register custom dashboard display
@app.formatter.register("dashboard")
def _dashboard_display(data, meta):
    """Custom dashboard display for termtap overview.

    Args:
        data: Dashboard data dictionary.
        meta: Display metadata.

    Returns:
        Formatted dashboard string.
    """
    from replkit2.textkit import compose, box, table, tree

    components = []

    if "summary" in data:
        components.append(box(data["summary"], title="Termtap Status"))

    if "sessions" in data and data["sessions"]:
        components.append(box(table(data["sessions"], headers=["Session", "Attached"]), title="Active Sessions"))

    if "commands" in data and data["commands"]:
        components.append(box(table(data["commands"], headers=["ID", "Command", "Elapsed"]), title="Running Commands"))

    if "targets" in data:
        components.append(box(tree(data["targets"]), title="Available Targets"))

    return compose(*components, spacing=1)


# REPL command: Dashboard overview
@app.command(display="dashboard", fastmcp={"enabled": False})
def dashboard(state: TermTapState) -> dict:
    """Show termtap dashboard overview.

    Args:
        state: Application state.

    Returns:
        Dashboard data dictionary.
    """
    import time

    sessions = []
    for s in state.sessions:
        sessions.append({"Session": s.name, "Attached": "Yes" if s.attached != "0" else "No"})

    commands = []
    for cmd_id, info in state.active_commands.items():
        elapsed = time.time() - info["started"]
        commands.append(
            {
                "ID": cmd_id[:8],
                "Command": info["command"][:30] + ("..." if len(info["command"]) > 30 else ""),
                "Elapsed": f"{elapsed:.1f}s",
            }
        )

    targets = {}
    for name, config in state.config.items():
        info = []
        if config.get("dir", ".") != ".":
            info.append(f"dir: {config['dir']}")
        if config.get("start"):
            info.append(f"start: {config['start']}")
        targets[name] = info if info else ["(no config)"]

    return {
        "summary": f"{len(sessions)} sessions | {len(commands)} active | {len(targets)} targets",
        "sessions": sessions,
        "commands": commands,
        "targets": targets,
    }


# REPL command: Show stream usage
@app.command(display="bar_chart", fastmcp={"enabled": False})
def streams(state: TermTapState) -> dict:
    """Show stream file sizes.

    Args:
        state: Application state.

    Returns:
        Dictionary mapping stream names to sizes in KB.
    """
    from pathlib import Path

    stream_dir = Path("/tmp/termtap/streams")
    if not stream_dir.exists():
        return {}

    sizes = {}
    for stream_file in stream_dir.glob("*.stream"):
        name = stream_file.stem.replace("_0.0", "")
        size_kb = stream_file.stat().st_size / 1024
        sizes[name] = int(size_kb)

    return sizes if sizes else {"(no streams)": 0}
