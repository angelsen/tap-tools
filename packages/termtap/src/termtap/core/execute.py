"""Command execution - pane-first architecture.

PUBLIC API:
  - execute: Execute command in tmux pane with streaming output
  - ExecutorState: State container for stream management
  - CommandResult: Result of command execution (imported from types)
"""

import uuid
import logging
import time
from dataclasses import dataclass, field

from ..types import Target, CommandResult
from ..tmux import get_or_create_session, send_keys
from ..tmux.utils import resolve_target_to_pane
from ..tmux.stream import _StreamManager
from ..config import get_pane_config
from ..process.detector import detect_process, get_handler_for_pane

logger = logging.getLogger(__name__)


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
    """Execute command in tmux pane with hook support.

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
        target: Target specification (pane ID, session:window.pane, or convenience).
        wait: Whether to wait for completion. Defaults to True.
        timeout: Maximum seconds to wait. Defaults to 30.0.

    Returns:
        CommandResult with output and status.
    """
    # Resolve target to pane
    try:
        pane_id, session_window_pane = resolve_target_to_pane(target)
    except RuntimeError:
        # Target doesn't exist - might be new session
        if target == "default" or ":" in target or target.startswith("%"):
            # Can't create these formats
            return CommandResult(
                output=f"Target not found: {target}",
                status="running",
                pane_id="",
                session_window_pane="",
                process=None
            )
        
        # Create new session for convenience format
        session = target
        config = get_pane_config(f"{session}:0.0")
        get_or_create_session(session, config.absolute_dir)
        
        # Now resolve again
        pane_id, session_window_pane = resolve_target_to_pane(target)
    
    # Get stream for this pane
    stream = state.stream_manager.get_stream(pane_id, session_window_pane)
    
    if not stream.start():
        logger.error(f"Failed to start streaming for pane {pane_id}")

    cmd_id = f"cmd_{uuid.uuid4().hex[:8]}"
    stream.mark_command(cmd_id, command)

    # HOOK: before_send - based on current process in pane
    send_info = detect_process(pane_id)
    send_handler = get_handler_for_pane(pane_id, send_info.process) if send_info.process else None

    if send_handler:
        modified_command = send_handler.before_send(pane_id, command)
        if modified_command is None:
            return CommandResult(
                output="Command cancelled by handler",
                status="aborted",
                pane_id=pane_id,
                session_window_pane=session_window_pane,
                process=send_info.process if send_info.process else send_info.shell,
            )
        command = modified_command

    send_keys(pane_id, command)

    # HOOK: after_send
    if send_handler:
        send_handler.after_send(pane_id, command)

    if not wait:
        # For non-wait, return the process that received the command
        return CommandResult(
            output="",
            status="running",
            pane_id=pane_id,
            session_window_pane=session_window_pane,
            process=send_info.process if send_info.process else send_info.shell,
        )

    start_time = time.time()

    # Small delay to let process start
    time.sleep(0.1)

    # Detect what process is NOW running (might be different!)
    wait_info = detect_process(pane_id)
    wait_handler = get_handler_for_pane(pane_id, wait_info.process) if wait_info.process else None

    # Wait loop with during_command hook
    while time.time() - start_time < timeout:
        info = detect_process(pane_id)
        elapsed = time.time() - start_time

        # HOOK: during_command - let handler check execution
        if wait_handler and not wait_handler.during_command(pane_id, elapsed):
            output = stream.read_from_mark(cmd_id)
            stream.mark_read("last_read")  # Mark as read for bash command
            return CommandResult(
                output=output, 
                status="aborted", 
                pane_id=pane_id,
                session_window_pane=session_window_pane,
                process=info.process if info.process else info.shell
            )

        if info.state == "ready":
            # Process is ready - command completed
            output = stream.read_from_mark(cmd_id)
            stream.mark_read("last_read")  # Mark as read for bash command
            duration = time.time() - start_time

            # HOOK: after_complete
            if wait_handler:
                wait_handler.after_complete(pane_id, command, duration)

            # Use process if available, otherwise use shell
            process_type = info.process if info.process else info.shell
            return CommandResult(
                output=output, 
                status="completed", 
                pane_id=pane_id,
                session_window_pane=session_window_pane,
                process=process_type
            )

        time.sleep(0.1)

    # Timeout reached
    final_info = detect_process(pane_id)
    output = stream.read_from_mark(cmd_id)
    stream.mark_read("last_read")  # Mark as read even on timeout
    return CommandResult(
        output=output,
        status="timeout",
        pane_id=pane_id,
        session_window_pane=session_window_pane,
        process=final_info.process if final_info.process else final_info.shell,
    )