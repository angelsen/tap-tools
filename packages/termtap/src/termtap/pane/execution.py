"""Direct command execution with handler lifecycle management.

PUBLIC API:
  - send_command: Execute command in pane with handler lifecycle
  - send_keys: Send raw keystrokes to pane
  - send_interrupt: Send interrupt signal to pane
"""

import re
import time
from typing import Optional, Any, Pattern

from .core import Pane, process_scan


def _check_ready(pane: Pane, compiled_pattern: Optional[Pattern] = None) -> bool:
    """Check if pane is ready via pattern or handler.

    Args:
        pane: The pane to check.
        compiled_pattern: Optional compiled regex pattern to match.
    """
    # Pattern matching takes precedence over handler logic
    if compiled_pattern and pane.visible_content:
        if compiled_pattern.search(pane.visible_content):
            return True

    is_ready, _ = pane.handler.is_ready(pane)
    # Convert three-state to binary for execution safety
    return bool(is_ready)


def _determine_status(elapsed: float, timeout: Optional[float]) -> str:
    """Determine final command status based on timing.

    Args:
        elapsed: Time elapsed since command start.
        timeout: Timeout threshold (None means no timeout).
    """
    if timeout is None:
        return "completed"
    return "timeout" if elapsed >= timeout else "completed"


def _build_result(
    pane: Pane, command: str, status: str, start_time: float, output: str = "", error: Optional[str] = None
) -> dict[str, Any]:
    """Build standard execution result dict.

    Args:
        pane: The pane (with cached process info).
        command: The command/keys that were sent.
        status: Status string (completed, timeout, sent, failed, etc.).
        start_time: When execution started (for elapsed calculation).
        output: Captured output (already filtered).
        error: Optional error message.
    """
    result = {
        "status": status,
        "command": command,
        "pane": pane.session_window_pane,
        "output": output,
        "elapsed": time.time() - start_time,
        "process": pane.process.name if pane.process else None,
        "shell": pane.shell.name if pane.shell else None,
        "handler": type(pane.handler).__name__,
        "language": (pane.process.name if pane.process else pane.shell.name if pane.shell else None) or "text",
    }

    if error:
        result["error"] = error

    return result


def send_command(
    pane: Pane,
    command: str,
    wait: bool = True,
    timeout: Optional[float] = None,
    ready_pattern: Optional[str] = None,
    grace_period: float = 0.5,
    state=None,
) -> dict[str, Any]:
    """Execute command in pane with handler lifecycle.

    Optimized execution with minimal process scans for performance.
    Supports both synchronous waiting and fire-and-forget modes.

    Args:
        pane: Target pane.
        command: Command to execute.
        wait: Whether to wait for completion. Defaults to True.
        timeout: Maximum wait time in seconds. None means no timeout.
        ready_pattern: Optional regex pattern to match for readiness.
        grace_period: Seconds to wait after completion before capturing output. Defaults to 0.5.
        state: Application state for caching (optional).

    Returns:
        Dict with status, output, elapsed time, and metadata.
    """
    start_time = time.time()

    with process_scan(pane.pane_id):
        handler = pane.handler

        # Handler can modify or cancel command
        modified = handler.before_send(pane, command)
        if modified is None:
            return _build_result(pane, command, "cancelled", start_time, error="Command cancelled by handler")

        command = modified

    from ..tmux.stream import _Stream

    stream = _Stream(pane.pane_id, pane.session_window_pane)
    if not stream.is_active():
        stream.start()

    cmd_id = f"cmd_{int(time.time() * 1000)}"
    cmd_id = stream.mark_command(cmd_id, command)

    # Let handler control how to send
    try:
        success = handler.send_to_pane(pane, command)
        if not success:
            return _build_result(pane, command, "failed", start_time, error="Failed to send command to pane")
    except Exception as e:
        return _build_result(pane, command, "failed", start_time, error=str(e))

    handler.after_send(pane, command)

    if not wait:
        stream.mark_command_end(cmd_id)

        with process_scan(pane.pane_id):
            output = pane.handler.capture_output(pane, cmd_id, state)
            return _build_result(pane, command, "sent", start_time, output)

    final_handler = handler
    completed = False

    compiled_pattern = re.compile(ready_pattern) if ready_pattern else None

    with process_scan(pane.pane_id):
        current_handler = pane.handler
        is_ready = _check_ready(pane, compiled_pattern)

        if is_ready:
            final_handler = current_handler
            completed = True

    if not completed:
        time.sleep(0.02)

        if timeout is None:
            timeout_at = float("inf")
        else:
            timeout_at = start_time + timeout

        while time.time() < timeout_at:
            with process_scan(pane.pane_id):
                current_handler = pane.handler
                is_ready = _check_ready(pane, compiled_pattern)

                if is_ready:
                    final_handler = current_handler
                    completed = True
                    break

                elapsed = time.time() - start_time
                if not current_handler.during_command(pane, elapsed):
                    return _build_result(pane, command, "aborted", start_time, error="Aborted by handler")

            time.sleep(0.1)

    time.sleep(grace_period)

    elapsed = time.time() - start_time
    status = _determine_status(elapsed, timeout)

    stream.mark_command_end(cmd_id)

    with process_scan(pane.pane_id):
        filtered_output = final_handler.capture_output(pane, cmd_id, state)

        final_handler.after_complete(pane, command, elapsed)

        return _build_result(pane, command, status, start_time, filtered_output)


def send_interrupt(pane: Pane) -> dict[str, Any]:
    """Send interrupt signal to pane.

    Delegates to handler's interrupt method for process-specific behavior.
    Handlers may implement special interrupt logic beyond simple Ctrl+C.

    Args:
        pane: Target pane.

    Returns:
        Dict with execution results.
    """
    start_time = time.time()

    with process_scan(pane.pane_id):
        handler = pane.handler
        success, message = handler.interrupt(pane)

        time.sleep(0.02)

        filtered_output = handler.capture_output(pane)

        status = "sent" if success else "failed"
        error = None if success else (message or "Failed to send interrupt")

        return _build_result(pane, "C-c", status, start_time, filtered_output, error)


def send_keys(pane: Pane, keys: str, enter: bool = False) -> dict[str, Any]:
    """Send raw keystrokes to pane.

    Bypasses command processing and handler lifecycle for direct key input.
    Useful for navigation keys, special characters, and interactive responses.

    Args:
        pane: Target pane.
        keys: Space-separated keys to send (e.g., "Up", "Down Down", "C-c").
        enter: Whether to add Enter key at the end. Defaults to False.

    Returns:
        Dict with execution results.
    """
    start_time = time.time()
    key_list = keys.split() if keys.strip() else []

    from ..tmux.pane import send_keys as tmux_send_keys

    try:
        success = tmux_send_keys(pane.pane_id, *key_list, enter=enter)
    except Exception as e:
        with process_scan(pane.pane_id):
            return _build_result(pane, keys, "failed", start_time, error=str(e))

    if not success:
        with process_scan(pane.pane_id):
            return _build_result(pane, keys, "failed", start_time, error="Failed to send keys")

    time.sleep(0.02)

    with process_scan(pane.pane_id):
        filtered_output = pane.handler.capture_output(pane)

        return _build_result(pane, keys, "sent", start_time, filtered_output)
