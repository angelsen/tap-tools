"""Internal Python handler for REPL and script processes.

# to_agent: Required per handlers/README.md
TESTING LOG:
Date: 2025-08-07
System: Linux 6.12.39-1-lts
Process: python v3.12.11, python3, python3.11 (via uv), ipython v9.4.0, termtap v1.0
Tracking: ~/.termtap/tracking/20250807_212502_printTesting_system_Python
         ~/.termtap/tracking/20250807_212924_import_time_timesleep5
         ~/.termtap/tracking/20250807_212324_python
         ~/.termtap/tracking/20250730_000831_python3
         ~/.termtap/tracking/20250730_001146_uv_run_python
         ~/.termtap/tracking/20250807_234622_if_True______print

Observed wait_channels:
- do_select: Python REPL waiting for input (ready)
- do_sys_poll: Python REPL polling for input (ready)
- do_epoll_wait: IPython waiting for input (ready)
- do_wait: Python waiting for subprocess (working)
- hrtimer_nanosleep: Python during sleep/timing operations (working)

Notes:
- do_sys_poll is the most common ready state for Python 3.12.11
- do_select is used by termtap REPL for input waiting
- do_epoll_wait is specific to IPython interactive sessions
- hrtimer_nanosleep clearly indicates Python is executing time.sleep() or similar
- Both python3 and system python show same wait_channel patterns
- uv run python executes python3.11, system python is 3.12.11
- termtap is a Python REPL application running under uv
"""

from . import ProcessHandler
from ...pane import Pane


class _PythonHandler(ProcessHandler):
    """Handler for Python processes including REPL and scripts."""

    handles = ["python", "python3", "python3.11", "python3.12", "python3.13", "ipython", "termtap"]

    def can_handle(self, pane: Pane) -> bool:
        """Check if this handler manages Python processes."""
        return bool(pane.process and pane.process.name in self.handles)

    def is_ready(self, pane: Pane) -> tuple[bool | None, str]:
        """Determine if Python is ready for input using wait channel patterns.

        Args:
            pane: Pane with process information.
        """
        if not pane.process:
            return True, "at shell prompt"

        if pane.process.has_children:
            return False, "has subprocess"

        # Ready states
        if pane.process.wait_channel == "do_select":
            return True, "termtap/Python REPL waiting"

        if pane.process.wait_channel == "do_sys_poll":
            return True, "REPL polling for input"

        if pane.process.wait_channel == "do_epoll_wait":
            return True, "IPython waiting for input"

        # Working states
        if pane.process.wait_channel == "do_wait":
            return False, "waiting for subprocess"

        if pane.process.wait_channel == "hrtimer_nanosleep":
            return False, "executing sleep/timing operation"
        return None, f"unrecognized wait_channel: {pane.process.wait_channel}"

    def _apply_filters(self, raw_output: str) -> str:
        """Apply minimal filtering for Python REPL output.

        Args:
            raw_output: Raw captured output.
        """
        from ...filters import strip_trailing_empty_lines

        return strip_trailing_empty_lines(raw_output)
