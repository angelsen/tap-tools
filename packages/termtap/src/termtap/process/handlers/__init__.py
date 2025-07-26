"""Process-specific handlers for different types of processes.

Provides customized behavior for command execution lifecycle based on process type.
Handler classes are internal - only the base class and factory function are public.

PUBLIC API:
  - ProcessHandler: Base abstract class for all process handlers
  - get_handler: Get the appropriate handler for a given process
"""

from abc import ABC, abstractmethod

from ..tree import ProcessNode


class ProcessHandler(ABC):
    """Base handler for process detection."""

    @abstractmethod
    def can_handle(self, process: ProcessNode) -> bool:
        """Check if this handler can handle this process."""
        pass

    @abstractmethod
    def is_ready(self, process: ProcessNode) -> tuple[bool, str]:
        """Check if process is ready for input.

        Args:
            process: The ProcessNode to check (already has all info)

        Returns:
            (is_ready, reason) tuple
        """
        pass

    def interrupt(self, session_id: str) -> tuple[bool, str]:
        """Send interrupt signal to process.

        Default: Ctrl+C
        Override for special behavior.

        Args:
            session_id: Tmux session ID

        Returns:
            (success, message) tuple
        """
        from ...tmux import send_keys

        success = send_keys(session_id, "C-c")
        return success, "sent Ctrl+C"

    # Hook lifecycle for command execution
    def before_send(self, session_id: str, command: str) -> str | None:
        """Called before sending command.

        Can modify or cancel command.

        Args:
            session_id: Tmux session ID
            command: Command to be sent

        Returns:
            Modified command or None to cancel
        """
        return command  # Default: pass through

    def after_send(self, session_id: str, command: str) -> None:
        """Called after command is sent.

        For logging, metrics, etc.

        Args:
            session_id: Tmux session ID
            command: Command that was sent
        """
        pass  # Default: no-op

    def during_command(self, session_id: str, elapsed: float) -> bool:
        """Called while waiting for command to complete.

        Args:
            session_id: Tmux session ID
            elapsed: Seconds elapsed since command started

        Returns:
            True to continue waiting, False to stop waiting
        """
        return True  # Default: always continue

    def after_complete(self, session_id: str, command: str, duration: float) -> None:
        """Called after command completes (ready state reached).

        For logging, cleanup, etc.

        Args:
            session_id: Tmux session ID
            command: Command that was executed
            duration: Total execution time in seconds
        """
        pass  # Default: no-op


# Handler instances - loaded lazily
_handlers = []


def get_handler(process: ProcessNode) -> ProcessHandler:
    """Get handler for a process."""
    global _handlers

    # Load handlers on first use
    if not _handlers:
        from .python import PythonHandler
        from .ssh import SSHHandler
        from .default import DefaultHandler

        # Order matters - first match wins
        _handlers = [
            PythonHandler(),
            SSHHandler(),
            DefaultHandler(),  # Must be last - handles everything else
        ]

    for handler in _handlers:
        if handler.can_handle(process):
            return handler

    # Should never reach here if DefaultHandler is last
    raise RuntimeError(f"No handler for process {process.name}")


__all__ = [
    "ProcessHandler",
    "get_handler",
]
