"""Command execution orchestration.

PUBLIC API:
  - execute: Execute command in tmux session
  - get_result: Get result of async command
  - ExecutorState: State container for command execution
  - abort_command: Abort a running command"""

import time
import uuid
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
import logging

from ..tmux import (
    get_or_create_session,
    send_keys,
    session_exists,
)
from ..tmux.stream import _StreamManager, _get_pane_for_session
from ..tmux.utils import _run_tmux
from ..config import get_target_config
from ..process.detect import _detect_shell_from_pane
from ..process.state import _wait_for_ready_state
from .command import _prepare_command
from .watcher import _wait_with_patterns

logger = logging.getLogger(__name__)


@dataclass
class _CommandResult:
    """Result of command execution.

    Attributes:
        output: Command output text
        status: Completion status (completed, timeout, aborted, running)
        cmd_id: Unique command identifier
        elapsed: Execution time in seconds
        session: Session name where command ran
    """

    output: str
    status: str  # completed, timeout, aborted, running
    cmd_id: Optional[str] = None
    elapsed: Optional[float] = None
    session: Optional[str] = None


@dataclass
class ExecutorState:
    """State for executor.

    Attributes:
        stream_manager: Manages tmux pane streams
        active_commands: Tracking for running commands
    """

    stream_manager: _StreamManager = field(default_factory=_StreamManager)
    active_commands: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def get_project_id(self) -> str:
        """Get project ID from current directory.

        Returns:
            Project ID based on directory path
        """
        cwd = Path.cwd()
        parts = cwd.parts
        if len(parts) >= 2:
            return f"{parts[-2]}-{parts[-1]}"
        return parts[-1] if parts else "default"


def execute(
    state: ExecutorState,
    command: str,
    target: str = "default",
    wait: bool = True,
    timeout: float = 30.0,
    hover_check: Optional[callable] = None,
) -> _CommandResult:
    """Execute command with optional waiting.

    Args:
        state: Executor state
        command: Command to execute
        target: Target session name or existing session
        wait: Whether to wait for completion
        timeout: Timeout in seconds
        hover_check: Optional hover check callable

    Returns:
        CommandResult with output and status
    """
    # If target is "default" or not specified, generate Docker name
    if target == "default":
        config = get_target_config("default")
        session = get_or_create_session(None, config.absolute_dir)  # Generate name
    elif session_exists(target):
        # Target is an existing session
        session = target
        config = get_target_config("default")
    else:
        # Target might be a config target or new session name
        config = get_target_config(target)
        if config.name == target:
            # It's a valid config target, create session with that name
            session = get_or_create_session(target, config.absolute_dir)
        else:
            # Not a config target, use as session name with default config
            config = get_target_config("default")
            session = get_or_create_session(target, config.absolute_dir)

    pane_id = _get_pane_for_session(session)
    stream = state.stream_manager.get_stream(pane_id)

    # Start streaming if not already active
    if not stream.start():
        logger.error(f"Failed to start streaming for pane {pane_id}")

    # Detect shell and prepare command
    shell_type = _detect_shell_from_pane(pane_id)
    if shell_type:
        command = _prepare_command(command, shell_type)
    else:
        logger.warning(f"Could not detect shell for pane {pane_id}, sending command as-is")

    cmd_id = str(uuid.uuid4())[:8]

    # Mark position BEFORE sending to capture all output
    stream.mark_position(cmd_id)

    send_keys(pane_id, command)

    # Track active command
    state.active_commands[cmd_id] = {
        "command": command,
        "session": session,
        "target": target,
        "started": time.time(),
        "pane_id": pane_id,
    }

    if not wait:
        # Return immediately
        return _CommandResult(output="", status="running", cmd_id=cmd_id, session=session)

    # Get PID for process monitoring
    code, stdout, _ = _run_tmux(["display", "-p", "-t", pane_id, "#{pane_pid}"])
    if code != 0:
        logger.error(f"Failed to get PID for pane {pane_id}")
        # Fallback to old method
        output = stream.read_from(cmd_id)
        return _CommandResult(output=output, status="error", cmd_id=cmd_id, session=session)

    try:
        pid = int(stdout.strip())
    except ValueError:
        logger.error(f"Invalid PID: {stdout}")
        pid = None

    # Wait for completion using process state
    output = ""
    reason = "unknown"

    # Check for hover patterns
    hover_patterns = config.hover_patterns if hasattr(config, "hover_patterns") else []

    if hover_patterns and hover_check:
        # Use pattern detection with process state
        # TODO: Implement hybrid approach
        output, reason = _wait_with_patterns(
            stream=stream,
            cmd_id=cmd_id,
            patterns=hover_patterns,
            pattern_callback=hover_check,
            silence_period=1.0,
            timeout=timeout,
            abort_check=None,
        )
    else:
        # Use process-based ready detection
        if pid and _wait_for_ready_state(pid, timeout=timeout):
            output = stream.read_from(cmd_id)
            reason = "ready"
        else:
            # Timeout or error
            output = stream.read_from(cmd_id)
            reason = "timeout"

    # Remove from active commands
    cmd_info = state.active_commands.pop(cmd_id, {})
    elapsed = time.time() - cmd_info.get("started", time.time())

    # Map reason to status
    status_map = {
        "ready": "completed",  # Process ready for input
        "silence": "completed",
        "timeout": "timeout",
        "aborted": "aborted",
        "pattern_abort": "aborted",
        "pattern_complete": "completed",
    }

    return _CommandResult(
        output=output, status=status_map.get(reason, reason), cmd_id=cmd_id, elapsed=elapsed, session=session
    )


def _execute_async(state: ExecutorState, command: str, target: str = "default") -> _CommandResult:
    """Execute command asynchronously.

    Args:
        state: Executor state
        command: Command to execute
        target: Target session name

    Returns:
        Command result with running status
    """
    return execute(state, command, target, wait=False)


def get_result(state: ExecutorState, cmd_id: str) -> _CommandResult:
    """Get result of async command."""
    cmd_info = state.active_commands.get(cmd_id)

    if not cmd_info:
        # Check if we have stream data
        for stream in state.stream_manager.streams.values():
            if cmd_id in stream.positions:
                output = stream.read_from(cmd_id)
                return _CommandResult(
                    output=output,
                    status="completed",  # Assume completed if not active
                    cmd_id=cmd_id,
                )

        return _CommandResult(output="", status="not_found", cmd_id=cmd_id)

    pane_id = cmd_info["pane_id"]
    stream = state.stream_manager.get_stream(pane_id)
    output = stream.read_from(cmd_id)
    elapsed = time.time() - cmd_info["started"]

    return _CommandResult(output=output, status="running", cmd_id=cmd_id, elapsed=elapsed, session=cmd_info["session"])


def abort_command(state: ExecutorState, cmd_id: str) -> _CommandResult:
    """Abort a running command.

    Args:
        state: Executor state
        cmd_id: Command ID to abort

    Returns:
        Command result with aborted status
    """
    cmd_info = state.active_commands.get(cmd_id)

    if not cmd_info:
        return _CommandResult(output="", status="not_found", cmd_id=cmd_id)

    pane_id = cmd_info["pane_id"]
    send_keys(pane_id, "\x03")

    stream = state.stream_manager.get_stream(pane_id)
    output = stream.read_from(cmd_id)

    state.active_commands.pop(cmd_id)

    return _CommandResult(output=output, status="aborted", cmd_id=cmd_id, session=cmd_info["session"])
