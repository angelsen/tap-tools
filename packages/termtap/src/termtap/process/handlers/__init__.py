"""Process-specific handlers for different types of processes.

PUBLIC API:
  - ProcessHandler: Base abstract class for all process handlers
  - get_handler: Get the appropriate handler for a given process
"""

from abc import ABC, abstractmethod

from ...types import ProcessContext


class ProcessHandler(ABC):
    """Base abstract class for all process handlers.

    Provides lifecycle hooks for command execution and process state detection.
    Override methods to customize behavior for specific process types.

    All methods now receive a ProcessContext which provides:
    - pane_id: The tmux pane ID
    - process: The ProcessNode with all process information
    - session_window_pane: The canonical "session:0.0" format
    - capture_visible(): Method to get pane content for content-based detection
    - send_keys(): Method to send keystrokes to the pane
    """

    @abstractmethod
    def can_handle(self, ctx: ProcessContext) -> bool:
        """Check if this handler can handle this process.

        Args:
            ctx: ProcessContext with process and pane information.

        Returns:
            True if this handler can handle the process.
        """
        pass

    @abstractmethod
    def is_ready(self, ctx: ProcessContext) -> tuple[bool, str]:
        """Check if process is ready for input.

        Args:
            ctx: ProcessContext with process and pane information.

        Returns:
            Tuple of (is_ready, reason) indicating process state.
        """
        pass

    def interrupt(self, ctx: ProcessContext) -> tuple[bool, str]:
        """Send interrupt signal to process.

        Default implementation sends Ctrl+C. Override for special behavior.

        Args:
            ctx: ProcessContext with process and pane information.

        Returns:
            Tuple of (success, message) indicating result.
        """
        success = ctx.send_keys("C-c", enter=False)
        return success, "sent Ctrl+C"

    def before_send(self, ctx: ProcessContext, command: str) -> str | None:
        """Called before sending command.

        Can modify or cancel command execution.

        Args:
            ctx: ProcessContext with process and pane information.
            command: Command to be sent.

        Returns:
            Modified command or None to cancel.
        """
        return command

    def after_send(self, ctx: ProcessContext, command: str) -> None:
        """Called after command is sent.

        Args:
            ctx: ProcessContext with process and pane information.
            command: Command that was sent.
        """
        pass

    def during_command(self, ctx: ProcessContext, elapsed: float) -> bool:
        """Called while waiting for command to complete.

        Args:
            ctx: ProcessContext with process and pane information.
            elapsed: Seconds elapsed since command started.

        Returns:
            True to continue waiting, False to stop waiting.
        """
        return True

    def after_complete(self, ctx: ProcessContext, command: str, duration: float) -> None:
        """Called after command completes.

        Args:
            ctx: ProcessContext with process and pane information.
            command: Command that was executed.
            duration: Total execution time in seconds.
        """
        pass


_handlers = []


def get_handler(ctx: ProcessContext) -> ProcessHandler:
    """Get the appropriate handler for a given process context.

    Args:
        ctx: ProcessContext with process and pane information.

    Returns:
        The appropriate ProcessHandler instance. Always returns a handler -
        uses DefaultHandler as fallback.
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
        if handler.can_handle(ctx):
            return handler

    # This should never happen if DefaultHandler is properly registered
    # Log warning and return DefaultHandler as safety fallback
    import logging

    logger = logging.getLogger(__name__)
    logger.warning(f"Handler list misconfigured - no handler for {ctx.process.name}, using DefaultHandler")
    from .default import _DefaultHandler

    return _DefaultHandler()


__all__ = [
    "ProcessHandler",
    "get_handler",
]
