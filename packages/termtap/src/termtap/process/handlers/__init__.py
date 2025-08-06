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
        """Called before sending command.

        Can modify or cancel command execution.

        Args:
            pane: Target pane.
            command: Command to be sent.

        Returns:
            Modified command or None to cancel.
        """
        return command

    def after_send(self, pane: Pane, command: str) -> None:
        """Called after command is sent.

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

    def capture_output(
        self, pane: Pane, cmd_id: str | None = None, method: str | None = None, filters: list | None = None
    ) -> str:
        """Capture and process command output with unified approach.

        Always start streaming provides cmd_id. Base class handles all capture methods
        and filtering. Pass empty list for raw output, None for sensible defaults.

        Args:
            pane: Target pane (process may have changed during execution).
            cmd_id: Stream command ID (always provided by execution pipeline).
            method: Capture method override ("stream", "visible", "last_n").
            filters: Filter functions to apply. None=defaults, []=raw output.

        Returns:
            Processed output ready for display.
        """
        # Default method: streaming for clean command output
        capture_method = method or "stream"

        # Capture based on method
        if capture_method == "stream" and cmd_id:
            from ...pane.streaming import get_command_output

            raw_output = get_command_output(pane, cmd_id, as_displayed=True)
        elif capture_method == "visible":
            from ...tmux.pane import capture_visible

            raw_output = capture_visible(pane.pane_id)
        elif capture_method == "last_n":
            from ...tmux.pane import capture_last_n

            raw_output = capture_last_n(pane.pane_id, 50)
        else:
            # Fallback to visible if streaming not available
            from ...tmux.pane import capture_visible

            raw_output = capture_visible(pane.pane_id)

        if not raw_output:
            return ""

        # Apply filtering: signature filters OR sensible defaults (not both)
        if filters is not None:
            # Explicit filters passed - use only these (empty list = raw output)
            output = raw_output
            for filter_func in filters:
                output = filter_func(output)
            return output
        else:
            # No filters specified - use sensible defaults
            from ...filters import strip_trailing_empty_lines, collapse_empty_lines

            output = strip_trailing_empty_lines(raw_output)
            output = collapse_empty_lines(output, threshold=5)
            return output


_handlers = []


def get_handler(pane: Pane) -> ProcessHandler:
    """Get the appropriate handler for a given process.

    Searches registered handlers in priority order and returns the first one
    that can handle the process. Always returns a handler using DefaultHandler
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
            _DefaultHandler(),  # Keep default last
        ]

    for handler in _handlers:
        if handler.can_handle(pane):
            return handler

    # Safety fallback if no handler matches
    import logging

    logger = logging.getLogger(__name__)
    process_name = pane.process.name if pane.process else "shell"
    logger.warning(f"Handler list misconfigured - no handler for {process_name}, using DefaultHandler")
    from .default import _DefaultHandler

    return _DefaultHandler()


__all__ = [
    "ProcessHandler",
    "get_handler",
]
