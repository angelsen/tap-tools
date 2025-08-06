"""Default handler for standard processes.

Internal module - no public API.
"""

from . import ProcessHandler
from ...pane import Pane
from ...filters import collapse_empty_lines


class _DefaultHandler(ProcessHandler):
    """Default handler - simple 'no children = ready' logic."""

    def can_handle(self, pane: Pane) -> bool:
        """Handle everything as fallback."""
        return True

    def is_ready(self, pane: Pane) -> tuple[bool | None, str]:
        """Check readiness using shell wait state and process children.

        Args:
            pane: Pane with process information.

        Returns:
            Tuple of (readiness, description).
        """
        if pane.shell and pane.shell.wait_channel == "do_wait":
            if pane.process and not pane.process.children:
                return True, "interactive"
            return False, "working"
        return True, "idle"

    def filter_output(self, content: str) -> str:
        """Apply default filtering - collapse excessive empty lines.

        Args:
            content: Raw output content.

        Returns:
            Content with collapsed empty lines.
        """
        return collapse_empty_lines(content, threshold=5)
