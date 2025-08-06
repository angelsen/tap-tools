"""Direct command execution with minimal overhead and smart context management.

PUBLIC API:
  - send_command: Execute command in pane with handler lifecycle
  - send_keys: Send raw keystrokes to pane
  - send_interrupt: Send interrupt signal to pane
"""

import re
import time
from typing import Optional, Any, Pattern

from .core import Pane, process_scan


def _capture_and_filter(pane: Pane, handler=None) -> str:
    """Capture visible output and apply handler filtering.

    Should be called within a process_scan context.

    Args:
        pane: The pane to capture from
        handler: Optional handler to use for filtering (defaults to pane.handler)

    Returns:
        Filtered output string
    """
    from ..tmux.pane import capture_visible

    output = capture_visible(pane.pane_id)
    handler = handler or pane.handler
    return handler.filter_output(output) if output else ""


def _check_ready(pane: Pane, compiled_pattern: Optional[Pattern] = None) -> bool:
    """Check if pane is ready via pattern or handler.

    Should be called within a process_scan context.
    Pattern matching takes precedence over handler state.

    Args:
        pane: The pane to check
        compiled_pattern: Optional compiled regex pattern to match

    Returns:
        True if ready, False otherwise
    """
    # Pattern matching overrides handler state
    if compiled_pattern and pane.visible_content:
        if compiled_pattern.search(pane.visible_content):
            return True

    is_ready, _ = pane.handler.is_ready(pane)
    # Convert three-state handler logic to binary decision for execution safety
    return bool(is_ready)


def _determine_status(elapsed: float, timeout: float) -> str:
    """Determine final command status based on timing.

    Args:
        elapsed: Time elapsed since command start
        timeout: Timeout threshold

    Returns:
        Status string: "timeout" or "completed"
    """
    return "timeout" if elapsed >= timeout else "completed"


def _build_result(
    pane: Pane, command: str, status: str, start_time: float, output: str = "", error: Optional[str] = None
) -> dict[str, Any]:
    """Build standard execution result dict.

    Should be called within a process_scan context to avoid extra scans.

    Args:
        pane: The pane (with cached process info)
        command: The command/keys that were sent
        status: Status string (completed, timeout, sent, failed, etc.)
        start_time: When execution started (for elapsed calculation)
        output: Captured output (already filtered)
        error: Optional error message

    Returns:
        Standard result dict with all metadata
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
    pane: Pane, command: str, wait: bool = True, timeout: Optional[float] = None, ready_pattern: Optional[str] = None
) -> dict[str, Any]:
    """Execute command in pane with handler lifecycle.

    Optimized execution with minimal process scans for performance.
    Supports both synchronous waiting and fire-and-forget modes.

    Args:
        pane: Target pane.
        command: Command to execute.
        wait: Whether to wait for completion. Defaults to True.
        timeout: Maximum wait time in seconds. Defaults to 30.0.
        ready_pattern: Optional regex pattern to match for readiness.

    Returns:
        Dict with status, output, elapsed time, and metadata.
    """
    start_time = time.time()

    # === PRE-EXECUTION PHASE (1 scan) ===
    with process_scan(pane.pane_id):
        handler = pane.handler

        # Handler pre-processing with cancellation capability
        modified = handler.before_send(pane, command)
        if modified is None:
            return _build_result(pane, command, "cancelled", start_time, error="Command cancelled by handler")

        command = modified

    # === SEND PHASE (no scan needed) ===
    from ..tmux.pane import send_keys as tmux_send_keys, send_via_paste_buffer

    try:
        # Route multiline vs single-line commands to appropriate tmux method
        if "\n" in command:
            success = send_via_paste_buffer(pane.pane_id, command)
        else:
            success = tmux_send_keys(pane.pane_id, command)

        if not success:
            return _build_result(pane, command, "failed", start_time, error="Failed to send command to pane")
    except Exception as e:
        return _build_result(pane, command, "failed", start_time, error=str(e))

    # Post-send handler notification without additional scanning
    handler.after_send(pane, command)

    # If not waiting, return immediately
    if not wait:
        with process_scan(pane.pane_id):
            return _build_result(pane, command, "sent", start_time)

    # === WAIT PHASE (periodic scans) ===
    final_handler = handler
    actual_timeout = timeout or 30.0
    completed = False

    # Pre-compile regex pattern for performance
    compiled_pattern = re.compile(ready_pattern) if ready_pattern else None

    # Initial readiness check - many commands complete immediately
    with process_scan(pane.pane_id):
        current_handler = pane.handler
        is_ready = _check_ready(pane, compiled_pattern)

        if is_ready:
            final_handler = current_handler
            completed = True

    # If not ready, enter wait loop
    if not completed:
        # Brief startup delay for command initialization
        time.sleep(0.02)

        while time.time() - start_time < actual_timeout:
            with process_scan(pane.pane_id):
                current_handler = pane.handler
                is_ready = _check_ready(pane, compiled_pattern)

                if is_ready:
                    final_handler = current_handler
                    completed = True
                    break

                # Handler can abort execution during wait
                elapsed = time.time() - start_time
                if not current_handler.during_command(pane, elapsed):
                    return _build_result(pane, command, "aborted", start_time, error="Aborted by handler")

            time.sleep(0.1)

    # === POST-EXECUTION PHASE (1 scan) ===
    # Output settling delay before final capture
    time.sleep(0.02)

    elapsed = time.time() - start_time
    status = _determine_status(elapsed, actual_timeout)

    with process_scan(pane.pane_id):
        filtered_output = _capture_and_filter(pane, final_handler)

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

        # Capture interrupt output and response
        filtered_output = _capture_and_filter(pane, handler)

        status = "sent" if success else "failed"
        error = None if success else (message or "Failed to send interrupt")

        return _build_result(pane, "C-c", status, start_time, filtered_output, error)


def send_keys(pane: Pane, *keys: str, enter: bool = False) -> dict[str, Any]:
    """Send raw keystrokes to pane.

    Bypasses command processing and handler lifecycle for direct key input.
    Useful for navigation keys, special characters, and interactive responses.

    Args:
        pane: Target pane.
        *keys: Keys to send (e.g., "Up", "Down", "C-c").
        enter: Whether to add Enter key at the end. Defaults to False.

    Returns:
        Dict with execution results.
    """
    start_time = time.time()
    keys_str = " ".join(keys)

    from ..tmux.pane import send_keys as tmux_send_keys

    try:
        success = tmux_send_keys(pane.pane_id, *keys, enter=enter)
    except Exception as e:
        with process_scan(pane.pane_id):
            return _build_result(pane, keys_str, "failed", start_time, error=str(e))

    if not success:
        with process_scan(pane.pane_id):
            return _build_result(pane, keys_str, "failed", start_time, error="Failed to send keys")

    time.sleep(0.02)

    with process_scan(pane.pane_id):
        # Capture output reflecting key effects
        filtered_output = _capture_and_filter(pane)

        return _build_result(pane, keys_str, "sent", start_time, filtered_output)
