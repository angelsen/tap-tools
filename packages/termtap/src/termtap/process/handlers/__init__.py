"""Process handlers for termtap.

PUBLIC API:
  - ProcessHandler: Base class for all handlers
  - get_handler: Get handler for a process
"""

import time
from abc import ABC, abstractmethod
from typing import Optional

from ..tree import ProcessNode


class ProcessHandler(ABC):
    """Base handler for process detection."""

    @abstractmethod
    def can_handle(self, process: ProcessNode) -> bool:
        """Check if this handler can handle this process."""
        pass

    @abstractmethod
    def is_ready(self, session_id: str) -> tuple[bool, str]:
        """Check if process is ready for input."""
        pass

    def wait_until_ready(self, session_id: str, timeout: float = 30.0) -> bool:
        """Wait until ready with during_command hook."""
        start = time.time()
        while True:
            # Check if ready
            ready, _ = self.is_ready(session_id)
            if ready:
                return True

            # Call during hook
            elapsed = time.time() - start
            if not self.during_command(session_id, elapsed):
                return False  # Hook said stop

            # Check timeout
            if elapsed >= timeout:
                return False

            time.sleep(0.1)

    # Optional hooks
    def pre_send(self, session_id: str, command: str) -> Optional[str]:
        """Pre-send hook. Return None to cancel."""
        return command

    def during_command(self, session_id: str, elapsed: float) -> bool:
        """Called during command execution.

        Can perform any side effects: logging, metrics, abort checks, etc.

        Args:
            session_id: Tmux session ID
            elapsed: Seconds elapsed since command started

        Returns:
            True to continue waiting, False to stop waiting
        """
        return True  # Default: always continue


# Handler instances - loaded lazily
_handlers = []


def get_handler(process: ProcessNode) -> ProcessHandler:
    """Get handler for a process."""
    global _handlers

    # Load handlers on first use
    if not _handlers:
        from .claude import ClaudeHandler
        from .ssh import SSHHandler
        from .default import DefaultHandler

        # Order matters - first match wins
        _handlers = [
            ClaudeHandler(),
            SSHHandler(),
            DefaultHandler(),  # Must be last
        ]

    for handler in _handlers:
        if handler.can_handle(process):
            return handler

    # Should never reach here if DefaultHandler is last
    raise RuntimeError(f"No handler for process {process.name}")
