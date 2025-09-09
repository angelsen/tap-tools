"""Process-specific handlers for different types of processes.

PUBLIC API:
  - ProcessHandler: Base abstract class for all process handlers
  - get_handler: Get the appropriate handler for a given process
"""

from abc import ABC, abstractmethod

from ...pane import Pane


class ProcessHandler(ABC):
    """Base abstract class for all process handlers.

    Provides lifecycle hooks for command execution and process state detection.
    Override methods to customize behavior for specific process types.

    All methods receive a Pane which provides:
    - pane_id: The tmux pane ID
    - process: The active process (if any)
    - shell: The shell process
    - session_window_pane: The canonical "session:0.0" format
    - visible_content: Cached pane content for content-based detection
    """

    @abstractmethod
    def can_handle(self, pane: Pane) -> bool:
        """Check if this handler can handle this process.

        Args:
            pane: Pane with process information.

        Returns:
            True if this handler can handle the process.
        """
        pass

    @abstractmethod
    def is_ready(self, pane: Pane) -> tuple[bool | None, str]:
        """Check if process is ready for input.

        Args:
            pane: Pane with process information.

        Returns:
            Tuple of (readiness, description):
            - (True, description): Process is ready for input
            - (False, description): Process is busy/working
            - (None, description): Cannot determine state
        """
        pass

    def interrupt(self, pane: Pane) -> tuple[bool, str]:
        """Send interrupt signal to process.

        Default implementation sends Ctrl+C. Override for special behavior.

        Args:
            pane: Pane to interrupt.

        Returns:
            Tuple of (success, message) indicating result.
        """
        from ...tmux.pane import send_keys

        success = send_keys(pane.pane_id, "C-c", enter=False)
        return success, "sent Ctrl+C"

    def before_send(self, pane: Pane, command: str) -> str | None:
        """Called before sending command. DO NOT OVERRIDE - use _before_send_impl instead.

        Checks configuration first, then calls handler implementation.

        Args:
            pane: Target pane.
            command: Command to be sent.

        Returns:
            Modified command or None to cancel.
        """
        # Check configuration first
        from .config import _get_handler_config
        handler_name = self.__class__.__name__.replace("_", "").replace("Handler", "").upper()
        action, timeout = _get_handler_config().get_action(handler_name, command)
        
        if action == "auto":
            # Store for after_send to use
            self._auto_timeout = timeout
            return command  # Skip handler's before_send logic
        elif action == "never":
            return None  # Block command
        
        # No config match or "ask" - use handler's normal behavior
        return self._before_send_impl(pane, command)
    
    def _before_send_impl(self, pane: Pane, command: str) -> str | None:
        """Handler-specific before_send logic. Override this in subclasses.

        Args:
            pane: Target pane.
            command: Command to be sent.

        Returns:
            Modified command or None to cancel.
        """
        return command

    def after_send(self, pane: Pane, command: str) -> None:
        """Called after command is sent. DO NOT OVERRIDE - use _after_send_impl instead.

        Handles auto-accept timeout, then calls handler implementation.

        Args:
            pane: Target pane.
            command: Command that was sent.
        """
        # If auto-accepted, handle timeout and skip handler logic
        if hasattr(self, '_auto_timeout'):
            import time
            time.sleep(self._auto_timeout)
            del self._auto_timeout
            return
        
        # Use handler's normal behavior
        self._after_send_impl(pane, command)
    
    def _after_send_impl(self, pane: Pane, command: str) -> None:
        """Handler-specific after_send logic. Override this in subclasses.

        Args:
            pane: Target pane.
            command: Command that was sent.
        """
        pass

    def during_command(self, pane: Pane, elapsed: float) -> bool:
        """Called while waiting for command to complete.

        Args:
            pane: Target pane.
            elapsed: Seconds elapsed since command started.

        Returns:
            True to continue waiting, False to stop waiting.
        """
        return True

    def after_complete(self, pane: Pane, command: str, duration: float) -> None:
        """Called after command completes.

        Args:
            pane: Target pane.
            command: Command that was executed.
            duration: Total execution time in seconds.
        """
        pass

    def send_to_pane(self, pane: Pane, command: str) -> bool:
        """Send command to pane using appropriate method.

        Override to customize how commands are sent (chunking, escaping, etc).
        Default implementation chooses between send-keys and paste-buffer.

        Args:
            pane: Target pane.
            command: Command to send.

        Returns:
            True if sent successfully, False otherwise.
        """
        from ...tmux.pane import send_keys as tmux_send_keys, send_via_paste_buffer

        try:
            if "\n" in command:
                return send_via_paste_buffer(pane.pane_id, command)
            else:
                return tmux_send_keys(pane.pane_id, command)
        except Exception:
            return False

    def capture_output(self, pane: Pane, cmd_id: str | None = None, state=None, display_lines: int = 50) -> str:
        """Capture and process command output with handler-centric approach.

        Centralizes capture, filtering, caching, and subset logic. Handler decides
        capture method based on context (cmd_id presence) and applies process-specific
        filtering.

        Args:
            pane: Target pane.
            cmd_id: Command ID for stream capture (from execution pipeline).
            state: Application state for caching (optional).
            display_lines: Number of lines to return for display.

        Returns:
            Processed output subset ready for display.
        """
        import time

        # 1. Decide capture method based on context
        if cmd_id:
            # Stream method for command output
            from ...tmux.stream import _Stream

            stream = _Stream(pane.pane_id, pane.session_window_pane)
            raw_output = stream.read_command_output(cmd_id, as_displayed=True)
        else:
            # Full buffer for general reads
            from ...tmux.core import run_tmux

            code, raw_output, _ = run_tmux(["capture-pane", "-t", pane.pane_id, "-p", "-S", "-", "-E", "-"])
            raw_output = raw_output if code == 0 else ""

        # 2. Apply process-specific filters (override in subclasses)
        filtered = self._apply_filters(raw_output)

        # 3. Cache if state provided
        if state and filtered:
            from ...app import PaneCache

            state.read_cache[pane.session_window_pane] = PaneCache(
                content=filtered, timestamp=time.time(), lines_per_page=display_lines, source="handler"
            )

        # 4. Return display subset (last N lines)
        lines = filtered.splitlines()
        if len(lines) > display_lines:
            return "\n".join(lines[-display_lines:])
        return filtered

    def _apply_filters(self, raw_output: str) -> str:
        """Apply process-specific filters. Override in subclasses.

        Default implementation provides sensible filtering for most processes.

        Args:
            raw_output: Raw captured output.

        Returns:
            Filtered output.
        """
        from ...filters import strip_trailing_empty_lines, collapse_empty_lines

        output = strip_trailing_empty_lines(raw_output)
        output = collapse_empty_lines(output, threshold=5)
        return output


_handlers = []


def get_handler(pane: Pane) -> ProcessHandler:
    """Get the appropriate handler for a given process.

    Searches registered handlers in priority order and returns the first one
    that can handle the process. Always returns a handler using _DefaultHandler
    as fallback.

    Args:
        pane: Pane with process information.

    Returns:
        The appropriate ProcessHandler instance.
    """
    global _handlers

    if not _handlers:
        from .python import _PythonHandler
        from .ssh import _SSHHandler
        from .claude import _ClaudeHandler
        from .default import _DefaultHandler

        _handlers = [
            _ClaudeHandler(),
            _PythonHandler(),
            _SSHHandler(),
            _DefaultHandler(),
        ]

    for handler in _handlers:
        if handler.can_handle(pane):
            return handler

    # Safety fallback if no handler matches
    import logging

    _logger = logging.getLogger(__name__)
    process_name = pane.process.name if pane.process else "shell"
    _logger.warning(f"Handler list misconfigured - no handler for {process_name}, using _DefaultHandler")
    from .default import _DefaultHandler

    return _DefaultHandler()


__all__ = [
    "ProcessHandler",
    "get_handler",
]
