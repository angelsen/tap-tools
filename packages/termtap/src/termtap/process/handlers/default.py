"""Default handler for standard processes.

Internal module - no public API.
"""

from . import ProcessHandler
from ...types import ProcessContext


class _DefaultHandler(ProcessHandler):
    """Default handler - simple 'no children = ready' logic."""

    def can_handle(self, ctx: ProcessContext) -> bool:
        """Handle everything.

        Args:
            ctx: ProcessContext with process and pane information.

        Returns:
            Always True as this is the fallback handler.
        """
        return True

    def is_ready(self, ctx: ProcessContext) -> tuple[bool, str]:
        """Check readiness using simple rule: has children = working.

        Args:
            ctx: ProcessContext with process and pane information.

        Returns:
            Tuple of (is_ready, reason) based on child processes.
        """
        if ctx.process.has_children:
            return False, f"{ctx.process.name} has subprocess"
        else:
            return True, f"{ctx.process.name} idle"
