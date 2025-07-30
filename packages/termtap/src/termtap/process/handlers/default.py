"""Default handler for standard processes.

Internal module - no public API.
"""

from . import ProcessHandler
from ...pane import Pane


class _DefaultHandler(ProcessHandler):
    """Default handler - simple 'no children = ready' logic."""

    def can_handle(self, pane: Pane) -> bool:
        """Handle everything.

        Args:
            pane: Pane with process information.

        Returns:
            Always True as this is the fallback handler.
        """
        return True

    def is_ready(self, pane: Pane) -> tuple[bool, str]:
        """Check readiness using simple rule: has children = working.

        Args:
            pane: Pane with process information.

        Returns:
            Tuple of (is_ready, reason) based on child processes.
        """
        if pane.process and pane.process.has_children:
            return False, f"{pane.process.name} has subprocess"
        else:
            name = pane.process.name if pane.process else pane.shell.name if pane.shell else "unknown"
            return True, f"{name} idle"
