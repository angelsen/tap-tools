"""Default handler for standard processes.

Internal module - no public API.
"""

from . import ProcessHandler
from ..tree import ProcessNode


class _DefaultHandler(ProcessHandler):
    """Default handler - simple 'no children = ready' logic."""

    def can_handle(self, process: ProcessNode) -> bool:
        """Handle everything.

        Args:
            process: The ProcessNode to check.

        Returns:
            Always True as this is the fallback handler.
        """
        return True

    def is_ready(self, process: ProcessNode) -> tuple[bool, str]:
        """Check readiness using simple rule: has children = working.

        Args:
            process: The ProcessNode to check.

        Returns:
            Tuple of (is_ready, reason) based on child processes.
        """
        if process.has_children:
            return False, f"{process.name} has subprocess"
        else:
            return True, f"{process.name} idle"
