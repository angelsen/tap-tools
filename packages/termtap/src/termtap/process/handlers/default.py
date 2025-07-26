"""Default handler for standard processes.

Internal handler class - not part of public API.
Used as fallback for processes not handled by specific handlers.
"""

from . import ProcessHandler
from ..tree import ProcessNode


class DefaultHandler(ProcessHandler):
    """Default handler - simple 'no children = ready' logic."""

    def can_handle(self, process: ProcessNode) -> bool:
        """Handle everything (must be last in handler list)."""
        return True

    def is_ready(self, process: ProcessNode) -> tuple[bool, str]:
        """Check readiness using simple rule: has children = working.

        This handles 90% of cases perfectly.
        """
        if process.has_children:
            return False, f"{process.name} has subprocess"
        else:
            return True, f"{process.name} idle"
