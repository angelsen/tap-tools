"""SSH handler - handles SSH client connections.

Internal module - no public API.

TESTING LOG:
Date: 2025-07-30
System: Linux 6.12.39-1-lts
Process: ssh (OpenSSH client)
Tracking: ~/.termtap/tracking/20250730_001318_ssh_klaudone

Observed wait_channels:
- unix_stream_read_generic: SSH waiting for network data (ready)
- do_sys_poll: SSH polling for input/output (ready)

Notes:
- SSH shows different wait_channels but both indicate ready state
- Transitions between unix_stream_read_generic and do_sys_poll
- No working states observed during connection
"""

from . import ProcessHandler
from ...types import ProcessContext


class _SSHHandler(ProcessHandler):
    """Handler for SSH client connections."""

    handles = ["ssh"]

    def can_handle(self, ctx: ProcessContext) -> bool:
        """Check if this handler manages this process."""
        return ctx.process.name in self.handles

    def is_ready(self, ctx: ProcessContext) -> tuple[bool, str]:
        """Determine if SSH is ready for input.

        Based on tracking data observations.
        """
        # Check children first - most reliable
        if ctx.process.has_children:
            return False, f"{ctx.process.name} has subprocess"

        # Ready states observed in tracking
        if ctx.process.wait_channel == "unix_stream_read_generic":
            return True, f"{ctx.process.name} connected"

        if ctx.process.wait_channel == "do_sys_poll":
            return True, f"{ctx.process.name} connected"

        # Unknown state - we haven't observed this wait_channel
        return False, f"{ctx.process.name} unknown state"
