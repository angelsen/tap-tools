"""Command execution orchestration with hook-native design.

PUBLIC API:
  - execute: Execute command in tmux session with streaming output
  - ExecutorState: State container for stream management
  - CommandResult: Result of command execution
"""

import uuid
import logging
import time
from dataclasses import dataclass, field

from ..types import CommandStatus, Target
from ..tmux import get_or_create_session, send_keys, session_exists, get_pane_for_session
from ..tmux.stream import _StreamManager
from ..config import _get_target_config
from ..process.detector import detect_process, get_handler_for_session

logger = logging.getLogger(__name__)


@dataclass
class CommandResult:
    """Result of command execution.

    Attributes:
        output: Command output text.
        status: Completion status (completed, timeout, running, aborted).
        session: Session name where command ran.
        process: Process that executed the command.
    """

    output: str
    status: CommandStatus
    session: str
    process: str | None


@dataclass
class ExecutorState:
    """State container for stream management across executions.

    Attributes:
        stream_manager: Manager for tmux pane streams.
    """

    stream_manager: _StreamManager = field(default_factory=_StreamManager)


def execute(
    state: ExecutorState,
    command: str,
    target: Target = "default",
    wait: bool = True,
    timeout: float = 30.0,
) -> CommandResult:
    """Execute command in tmux session with hook support.

    Hook flow:
    1. before_send - Can modify/cancel command based on current process
    2. Send command
    3. after_send - Post-send actions
    4. Detect new process (might have changed!)
    5. during_command - Monitor execution with new process handler
    6. after_complete - Cleanup/logging

    Args:
        state: Executor state for stream management.
        command: Command to execute.
        target: Target specification (session name or "default"). Defaults to "default".
        wait: Whether to wait for completion. Defaults to True.
        timeout: Maximum seconds to wait. Defaults to 30.0.

    Returns:
        CommandResult with output and status.
    """
    config_target = target if target != "default" else "default"
    config = _get_target_config(config_target)

    # Determine session - use existing or create new
    if session_exists(target):
        session = target
    else:
        if target != "default":
            session = get_or_create_session(target, config.absolute_dir)
        else:
            # Get default session
            config = _get_target_config("default")
            session = get_or_create_session(target, config.absolute_dir)

    pane_id = get_pane_for_session(session)
    stream = state.stream_manager.get_stream(pane_id)

    if not stream.start():
        logger.error(f"Failed to start streaming for pane {pane_id}")

    mark_id = str(uuid.uuid4())[:8]
    stream.mark_position(mark_id)

    # HOOK: before_send - based on current process
    send_info = detect_process(session)
    send_handler = get_handler_for_session(session, send_info.process) if send_info.process else None

    if send_handler:
        modified_command = send_handler.before_send(session, command)
        if modified_command is None:
            return CommandResult(
                output="Command cancelled by handler",
                status="aborted",
                session=session,
                process=send_info.process if send_info.process else send_info.shell,
            )
        command = modified_command

    send_keys(pane_id, command)

    # HOOK: after_send
    if send_handler:
        send_handler.after_send(session, command)

    if not wait:
        # For non-wait, return the process that received the command
        return CommandResult(
            output="",
            status="running",
            session=session,
            process=send_info.process if send_info.process else send_info.shell,
        )

    start_time = time.time()

    # Small delay to let process start
    time.sleep(0.1)

    # Detect what process is NOW running (might be different!)
    wait_info = detect_process(session)
    wait_handler = get_handler_for_session(session, wait_info.process) if wait_info.process else None

    # Wait loop with during_command hook
    while time.time() - start_time < timeout:
        info = detect_process(session)
        elapsed = time.time() - start_time

        # HOOK: during_command - let handler check execution
        if wait_handler and not wait_handler.during_command(session, elapsed):
            output = stream.read_from(mark_id)
            return CommandResult(
                output=output, status="aborted", session=session, process=info.process if info.process else info.shell
            )

        if info.state == "ready":
            # Process is ready - command completed
            output = stream.read_from(mark_id)
            duration = time.time() - start_time

            # HOOK: after_complete
            if wait_handler:
                wait_handler.after_complete(session, command, duration)

            # Use process if available, otherwise use shell
            process_type = info.process if info.process else info.shell
            return CommandResult(output=output, status="completed", session=session, process=process_type)

        time.sleep(0.1)

    final_info = detect_process(session)
    output = stream.read_from(mark_id)
    return CommandResult(
        output=output,
        status="timeout",
        session=session,
        process=final_info.process if final_info.process else final_info.shell,
    )
