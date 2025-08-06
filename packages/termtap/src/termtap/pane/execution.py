"""Direct command execution with minimal overhead and smart context management."""

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
    # Check pattern first (takes precedence)
    if compiled_pattern and pane.visible_content:
        if compiled_pattern.search(pane.visible_content):
            return True

    # Check handler state
    is_ready, _ = pane.handler.is_ready(pane)
    # Treat None as False for execution decisions (safer to assume not ready)
    # This preserves the three-state logic in handlers while providing binary decision here
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
    """Send command to pane with minimal overhead.

    Uses 2-3 process scans total:
    1. Pre-execution (handler selection, before_send)
    2. Wait loop (only if waiting, periodic)
    3. Post-execution (output capture, filtering, after_complete)

    Args:
        pane: Target pane
        command: Command to execute
        wait: Whether to wait for completion
        timeout: Maximum wait time in seconds
        ready_pattern: Optional regex pattern to match for readiness (takes precedence)

    Returns:
        Dict with status, output, elapsed time, etc.
    """
    start_time = time.time()

    # === PRE-EXECUTION PHASE (1 scan) ===
    with process_scan(pane.pane_id):
        handler = pane.handler

        # Let handler modify/cancel command
        modified = handler.before_send(pane, command)
        if modified is None:
            return _build_result(pane, command, "cancelled", start_time, error="Command cancelled by handler")

        command = modified

    # === SEND PHASE (no scan needed) ===
    from ..tmux.pane import send_keys as tmux_send_keys, send_via_paste_buffer

    try:
        # Use paste buffer for multiline commands, regular send for single line
        if "\n" in command:
            success = send_via_paste_buffer(pane.pane_id, command)
        else:
            success = tmux_send_keys(pane.pane_id, command)

        if not success:
            return _build_result(pane, command, "failed", start_time, error="Failed to send command to pane")
    except Exception as e:
        return _build_result(pane, command, "failed", start_time, error=str(e))

    # After send hook (still using cached handler - no scan)
    handler.after_send(pane, command)

    # If not waiting, return immediately
    if not wait:
        # Need scan context for metadata
        with process_scan(pane.pane_id):
            return _build_result(pane, command, "sent", start_time)

    # === WAIT PHASE (periodic scans) ===
    final_handler = handler  # Track handler for post-execution
    actual_timeout = timeout or 30.0
    completed = False

    # Compile ready pattern once if provided
    compiled_pattern = re.compile(ready_pattern) if ready_pattern else None

    # Check immediately first - many commands complete instantly
    with process_scan(pane.pane_id):
        current_handler = pane.handler
        is_ready = _check_ready(pane, compiled_pattern)

        if is_ready:
            final_handler = current_handler
            completed = True

    # If not ready, enter wait loop
    if not completed:
        # Small initial delay for commands that need time to start
        time.sleep(0.02)  # 20ms

        while time.time() - start_time < actual_timeout:
            with process_scan(pane.pane_id):
                current_handler = pane.handler
                is_ready = _check_ready(pane, compiled_pattern)

                if is_ready:
                    final_handler = current_handler
                    completed = True
                    break

                # Let handler abort if needed
                elapsed = time.time() - start_time
                if not current_handler.during_command(pane, elapsed):
                    return _build_result(pane, command, "aborted", start_time, error="Aborted by handler")

            # Wait before next check
            time.sleep(0.1)

    # === POST-EXECUTION PHASE (1 scan) ===
    # Brief delay for output to settle (reduced from 100ms to 20ms)
    time.sleep(0.02)

    # Determine final status
    elapsed = time.time() - start_time
    status = _determine_status(elapsed, actual_timeout)

    with process_scan(pane.pane_id):
        # Capture and filter output
        filtered_output = _capture_and_filter(pane, final_handler)

        # Completion hook
        final_handler.after_complete(pane, command, elapsed)

        # Build result with all metadata
        return _build_result(pane, command, status, start_time, filtered_output)


def send_interrupt(pane: Pane) -> dict[str, Any]:
    """Send interrupt signal (Ctrl+C) to pane.

    Note: This delegates to the handler's interrupt method which
    may have special logic (e.g., Claude's two-step exit).

    Args:
        pane: Target pane

    Returns:
        Dict with execution results
    """
    start_time = time.time()

    with process_scan(pane.pane_id):
        handler = pane.handler
        success, message = handler.interrupt(pane)

        # Brief delay for output to settle
        time.sleep(0.02)

        # Capture output to show the ^C and any response
        filtered_output = _capture_and_filter(pane, handler)

        status = "sent" if success else "failed"
        error = None if success else (message or "Failed to send interrupt")

        return _build_result(pane, "C-c", status, start_time, filtered_output, error)


def send_keys(pane: Pane, *keys: str, enter: bool = False) -> dict[str, Any]:
    """Send raw keys to pane without command semantics.

    This is for sending special keys like arrows, tabs, etc.
    No handler lifecycle, no waiting, just raw key sending.

    Args:
        pane: Target pane
        *keys: Keys to send (e.g., "Up", "Down", "C-c")
        enter: Whether to add Enter key at the end

    Returns:
        Dict with execution results
    """
    start_time = time.time()
    keys_str = " ".join(keys)

    from ..tmux.pane import send_keys as tmux_send_keys

    try:
        success = tmux_send_keys(pane.pane_id, *keys, enter=enter)
    except Exception as e:
        # Return error immediately without scan
        with process_scan(pane.pane_id):
            return _build_result(pane, keys_str, "failed", start_time, error=str(e))

    if not success:
        with process_scan(pane.pane_id):
            return _build_result(pane, keys_str, "failed", start_time, error="Failed to send keys")

    # Brief delay for output to settle
    time.sleep(0.02)

    with process_scan(pane.pane_id):
        # Capture output to show effect of keys
        filtered_output = _capture_and_filter(pane)

        return _build_result(pane, keys_str, "sent", start_time, filtered_output)


# === POTENTIAL UPSTREAM IMPROVEMENTS ===
#
# 1. inspection.py could be optimized:
#    - read_output() calls pane.handler.filter_output() causing extra scan
#    - get_process_info() accesses many properties causing scans
#    - Both should assume they're called within scan context
#    - Or add context_aware=True parameter
#
# 2. tmux/pane.py could have unified send:
#    - send_command(pane_id, text) that handles multiline internally
#    - Would centralize the "\n" check logic
#
# 3. Consider removing streaming module entirely:
#    - Adds significant complexity
#    - Direct capture seems sufficient for most use cases
#    - Could be re-added later if needed
#
# 4. Handler interface could be simplified:
#    - Make during_command() optional (default returns True)
#    - Make filter_output() optional (default returns input unchanged)
#    - Only require is_ready() for core functionality
