"""Python process handler.

Internal handler class - not part of public API.
Specialized handler for Python processes (REPL and scripts).
"""

from . import ProcessHandler
from ..tree import ProcessNode


class PythonHandler(ProcessHandler):
    """Handler for Python processes - REPL and scripts."""

    handles = ["python", "python3", "python3.11", "python3.12", "python3.13"]

    def can_handle(self, process: ProcessNode) -> bool:
        """Check if this is a Python process."""
        return process.name in self.handles

    def is_ready(self, process: ProcessNode) -> tuple[bool, str]:
        """Check if Python process is ready.

        - Python REPL idle: do_sys_poll wait channel
        - Python running sleep(): hrtimer_nanosleep
        - Python script: has children (subprocess)
        """
        # Has children = running subprocess
        if process.has_children:
            return False, "python has subprocess"

        # Check wait channel for special states
        if process.wait_channel == "hrtimer_nanosleep":
            return False, "python running sleep()"

        # Python REPL ready: do_sys_poll
        if process.wait_channel == "do_sys_poll":
            return True, "python REPL waiting"

        # Other states - assume working
        return False, f"python {process.wait_channel or 'running'}"

    def interrupt(self, session_id: str) -> tuple[bool, str]:
        """Interrupt Python process.

        Sends Ctrl+C which:
        - In REPL: Cancels current line
        - Running code: Raises KeyboardInterrupt
        """
        from ...tmux import send_keys

        success = send_keys(session_id, "C-c")
        return success, "sent KeyboardInterrupt"
