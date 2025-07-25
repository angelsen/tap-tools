"""Command execution orchestration.

PUBLIC API:
  - execute: Execute command in tmux session with streaming output
  - ExecutorState: State container for stream management
"""

import uuid
import logging
from dataclasses import dataclass, field

from ..types import CommandStatus, Target
from ..tmux import get_or_create_session, send_keys, session_exists, get_pane_for_session
from ..tmux.stream import _StreamManager
from ..config import get_target_config
from ..process import wait_until_ready

logger = logging.getLogger(__name__)


@dataclass
class CommandResult:
    """Result of command execution.

    Attributes:
        output: Command output text
        status: Completion status (completed, timeout, running)
        session: Session name where command ran
    """
    output: str
    status: CommandStatus
    session: str


@dataclass
class ExecutorState:
    """State for executor - just holds the stream manager."""
    stream_manager: _StreamManager = field(default_factory=lambda: _StreamManager())


def execute(
    state: ExecutorState,
    command: str,
    target: Target = "default",
    wait: bool = True,
    timeout: float = 30.0,
) -> CommandResult:
    """Execute command with streaming output capture.

    Uses the streaming sidecar to reliably capture all output from the command.
    Process readiness is determined by the handler-based architecture.

    Args:
        state: Executor state containing stream manager
        command: Command to execute
        target: Target session name or config target
        wait: Whether to wait for completion
        timeout: Timeout in seconds

    Returns:
        CommandResult with output and status
    """
    # Resolve session name
    if target == "default":
        config = get_target_config("default")
        session = get_or_create_session(None, config.absolute_dir)  # Generate Docker name
    elif session_exists(target):
        # Target is an existing session
        session = target
    else:
        # Check if it's a config target
        config = get_target_config(target)
        if config.name == target:
            # Valid config target
            session = get_or_create_session(target, config.absolute_dir)
        else:
            # Use as session name with default config
            config = get_target_config("default")
            session = get_or_create_session(target, config.absolute_dir)

    # Get pane and start streaming
    pane_id = get_pane_for_session(session)
    stream = state.stream_manager.get_stream(pane_id)
    
    if not stream.start():
        logger.error(f"Failed to start streaming for pane {pane_id}")

    # Mark position before sending command
    mark_id = str(uuid.uuid4())[:8]
    stream.mark_position(mark_id)
    
    # Send the command
    send_keys(pane_id, command)
    
    if not wait:
        return CommandResult(
            output="",
            status="running",
            session=session
        )
    
    # Wait for process to be ready
    if wait_until_ready(session, timeout=timeout):
        output = stream.read_from(mark_id)
        return CommandResult(
            output=output,
            status="completed",
            session=session
        )
    else:
        # Timeout
        output = stream.read_from(mark_id)
        return CommandResult(
            output=output,
            status="timeout",
            session=session
        )