"""Default handler for standard processes.

Internal module - no public API.
"""

from . import ProcessHandler
from ...pane import Pane
from ...filters import collapse_empty_lines


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

    def is_ready(self, pane: Pane) -> tuple[bool | None, str]:
        """Check readiness: shell in do_wait = not ready, unless interactive.

        Enhanced logic:
        1. If shell is waiting (do_wait) AND process has no children -> interactive app ready
        2. If shell is waiting AND process has children -> still working
        3. If shell not waiting -> idle at prompt

        Args:
            pane: Pane with process information.

        Returns:
            Tuple of (readiness, description):
            - (False, "working"): Process is actively working
            - (True, "interactive"): Interactive app ready for input
            - (True, "idle"): Shell at prompt
            - Never returns None (always makes a determination)
        """
        # Check if shell is waiting for a child process
        if pane.shell and pane.shell.wait_channel == "do_wait":
            # Shell is waiting - check if it's an interactive app
            if pane.process and not pane.process.children:
                # Process exists but has no subprocesses - likely interactive
                return True, "interactive"
            # Process has children or doesn't exist - still working
            return False, "working"

        # Shell not in do_wait (or no shell), so it's ready
        return True, "idle"

    def filter_output(self, content: str) -> str:
        """Apply default filtering - collapse excessive empty lines.

        Args:
            content: Raw output content.

        Returns:
            Content with collapsed empty lines.
        """
        # Start with modest threshold of 5 empty lines
        return collapse_empty_lines(content, threshold=5)
