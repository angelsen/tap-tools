"""Process-specific handlers for different types of processes.

PUBLIC API:
  - ProcessHandler: Base abstract class for all process handlers
  - get_handler: Get the appropriate handler for a given process
"""

from abc import ABC, abstractmethod

from ..tree import ProcessNode


class ProcessHandler(ABC):
    """Base abstract class for all process handlers.

    Provides lifecycle hooks for command execution and process state detection.
    Override methods to customize behavior for specific process types.
    """

    @abstractmethod
    def can_handle(self, process: ProcessNode) -> bool:
        """Check if this handler can handle this process.

        Args:
            process: The ProcessNode to check.

        Returns:
            True if this handler can handle the process.
        """
        pass

    @abstractmethod
    def is_ready(self, process: ProcessNode) -> tuple[bool, str]:
        """Check if process is ready for input.

        Args:
            process: The ProcessNode to check.

        Returns:
            Tuple of (is_ready, reason) indicating process state.
        """
        pass

    def interrupt(self, pane_id: str) -> tuple[bool, str]:
        """Send interrupt signal to process.

        Default implementation sends Ctrl+C. Override for special behavior.

        Args:
            pane_id: Tmux pane ID.

        Returns:
            Tuple of (success, message) indicating result.
        """
        from ...tmux import send_keys

        success = send_keys(pane_id, "C-c")
        return success, "sent Ctrl+C"

    def before_send(self, pane_id: str, command: str) -> str | None:
        """Called before sending command.

        Can modify or cancel command execution.

        Args:
            session_id: Tmux session ID.
            command: Command to be sent.

        Returns:
            Modified command or None to cancel.
        """
        return command

    def after_send(self, pane_id: str, command: str) -> None:
        """Called after command is sent.

        Args:
            session_id: Tmux session ID.
            command: Command that was sent.
        """
        pass

    def during_command(self, pane_id: str, elapsed: float) -> bool:
        """Called while waiting for command to complete.

        Args:
            session_id: Tmux session ID.
            elapsed: Seconds elapsed since command started.

        Returns:
            True to continue waiting, False to stop waiting.
        """
        return True

    def after_complete(self, pane_id: str, command: str, duration: float) -> None:
        """Called after command completes.

        Args:
            session_id: Tmux session ID.
            command: Command that was executed.
            duration: Total execution time in seconds.
        """
        pass


_handlers = []


def get_handler(process: ProcessNode) -> ProcessHandler:
    """Get the appropriate handler for a given process.

    Args:
        process: The ProcessNode to get a handler for.

    Returns:
        The appropriate ProcessHandler instance.

    Raises:
        RuntimeError: If no handler can handle the process.
    """
    global _handlers

    if not _handlers:
        from .python import _PythonHandler
        from .ssh import _SSHHandler
        from .default import _DefaultHandler

        _handlers = [
            _PythonHandler(),
            _SSHHandler(),
            _DefaultHandler(),
        ]

    for handler in _handlers:
        if handler.can_handle(process):
            return handler

    raise RuntimeError(f"No handler for process {process.name}")


__all__ = [
    "ProcessHandler",
    "get_handler",
]
