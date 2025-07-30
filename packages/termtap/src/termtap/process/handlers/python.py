"""Python handler - handles Python REPL and scripts.

Internal module - no public API.

TESTING LOG:
Date: 2025-07-30
System: Linux 6.12.39-1-lts
Process: python3 v3.12.11, python3.11 (via uv)
Tracking: ~/.termtap/tracking/20250730_000831_python3
         ~/.termtap/tracking/20250730_001146_uv_run_python
         ~/.termtap/tracking/20250729_235235_python3_tmptest_subprocesspy

Observed wait_channels:
- do_select: Python REPL waiting for input (ready)
- do_wait: Python waiting for subprocess (working)

Notes:
- Both python3 and python3.11 show same wait_channel patterns
- uv run python executes python3.11
"""

from . import ProcessHandler
from ...pane import Pane


class _PythonHandler(ProcessHandler):
    """Handler for Python processes - REPL and scripts."""

    handles = ["python", "python3", "python3.11", "python3.12", "python3.13"]

    def can_handle(self, pane: Pane) -> bool:
        """Check if this handler manages this process."""
        return bool(pane.process and pane.process.name in self.handles)

    def is_ready(self, pane: Pane) -> tuple[bool, str]:
        """Determine if Python is ready for input.

        Based on tracking data observations.
        """
        if not pane.process:
            # No active process means we're at shell prompt
            return True, "at shell prompt"

        # Check children first - most reliable
        if pane.process.has_children:
            return False, f"{pane.process.name} has subprocess"

        # Ready state observed in tracking
        if pane.process.wait_channel == "do_select":
            return True, f"{pane.process.name} REPL waiting"

        # Working state observed in tracking
        if pane.process.wait_channel == "do_wait":
            return False, f"{pane.process.name} waiting for subprocess"

        # Unknown state - we haven't observed this wait_channel
        return False, f"{pane.process.name} unknown state"
