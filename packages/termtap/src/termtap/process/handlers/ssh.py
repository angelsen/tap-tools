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
from ...pane import Pane


class _SSHHandler(ProcessHandler):
    """Handler for SSH client connections."""

    handles = ["ssh"]

    def can_handle(self, pane: Pane) -> bool:
        """Check if this handler manages SSH processes."""
        return bool(pane.process and pane.process.name in self.handles)

    def is_ready(self, pane: Pane) -> tuple[bool | None, str]:
        """SSH is always ready - we can't detect remote state."""
        return True, "connected"

    def before_send(self, pane: Pane, command: str) -> str | None:
        """Show edit popup for SSH commands.

        Args:
            pane: Target pane.
            command: Command to be sent.

        Returns:
            Modified command or None to cancel.
        """
        from ...popup import Popup

        title = pane.title or "SSH Command"
        p = Popup(title=title)
        p.header("Remote Execution")
        p.warning(f"Command: {command}")

        edited = p.input(placeholder="Press Enter to execute or ESC to cancel", header="Edit command:", value=command)
        return edited if edited else None

    def after_send(self, pane: Pane, command: str) -> None:
        """Wait for user to indicate when remote command is done.

        Args:
            pane: Target pane.
            command: Command that was sent.
        """
        import time
        from ...popup import Popup
        from ...utils import truncate_command

        time.sleep(0.5)

        p = Popup(title=pane.title or "SSH Session")
        p.header("Waiting for Remote Command")
        p.info(f"Command: {truncate_command(command)}")
        p.text("")
        p.text("Press Enter when command completes")
        p._add_line("read -r")
        p.show()
