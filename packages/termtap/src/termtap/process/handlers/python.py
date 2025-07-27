"""Python process handler.

Internal module - no public API.
"""

from . import ProcessHandler
from ..tree import ProcessNode


class _PythonHandler(ProcessHandler):
    """Handler for Python processes - REPL and scripts."""

    handles = ["python", "python3", "python3.11", "python3.12", "python3.13"]

    def can_handle(self, process: ProcessNode) -> bool:
        """Check if this is a Python process.

        Args:
            process: The ProcessNode to check.

        Returns:
            True if process name matches Python executables.
        """
        return process.name in self.handles

    def is_ready(self, process: ProcessNode) -> tuple[bool, str]:
        """Check if Python process is ready.

        Uses wait channel and child process information to determine state.

        Args:
            process: The ProcessNode to check.

        Returns:
            Tuple of (is_ready, reason) based on Python-specific logic.
        """
        if process.has_children:
            return False, "python has subprocess"

        if process.wait_channel == "hrtimer_nanosleep":
            return False, "python running sleep()"

        if process.wait_channel == "do_sys_poll":
            return True, "python REPL waiting"

        return False, f"python {process.wait_channel or 'running'}"

    def interrupt(self, pane_id: str) -> tuple[bool, str]:
        """Interrupt Python process.

        Args:
            pane_id: Tmux pane ID.

        Returns:
            Tuple of (success, message) indicating result.
        """
        from ...tmux import send_keys

        success = send_keys(pane_id, "C-c")
        return success, "sent KeyboardInterrupt"
