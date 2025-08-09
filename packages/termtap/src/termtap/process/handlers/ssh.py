"""SSH handler - handles SSH client connections.

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

import hashlib
import os
import time
from . import ProcessHandler
from ...pane import Pane


class _SSHHandler(ProcessHandler):
    """Handler for SSH client connections."""

    handles = ["ssh"]

    # Track screenshot changes per pane_id to detect connection establishment
    _screenshot_tracking = {}

    def can_handle(self, pane: Pane) -> bool:
        """Check if this handler manages SSH processes."""
        return bool(pane.process and pane.process.name in self.handles)

    def _get_process_age(self, pid: int) -> float:
        """Get process age in seconds from /proc.

        Returns actual process age based on system uptime and process start time.
        """
        try:
            # Read stat file
            with open(f"/proc/{pid}/stat", "r") as f:
                stat = f.read()
            fields = stat[stat.rfind(")") + 1 :].strip().split()
            if len(fields) < 20:
                return 0.0

            starttime_ticks = int(fields[19])

            # Get system info
            hz = os.sysconf(os.sysconf_names.get("SC_CLK_TCK", 2))
            with open("/proc/uptime", "r") as f:
                uptime = float(f.read().split()[0])

            # Calculate age
            process_uptime = starttime_ticks / hz
            age = uptime - process_uptime
            return age
        except (IOError, OSError, ValueError, IndexError):
            return 0.0

    def is_ready(self, pane: Pane) -> tuple[bool | None, str]:
        """Check if SSH connection is established using screenshot stability.

        For new SSH processes, we track screenshot changes to detect when
        the connection is established (screen stabilizes after initial output).
        """
        if not pane.process:
            return True, "no_process"

        # Get actual process age from /proc
        process_age = self._get_process_age(pane.process.pid)

        # For established connections (> 5 seconds), always ready
        if process_age > 5.0:
            # Clean up any stale tracking
            if pane.pane_id in self._screenshot_tracking:
                del self._screenshot_tracking[pane.pane_id]
            return True, "connected"

        # For new connections, track screenshot stability
        pane_id = pane.pane_id
        if pane_id not in self._screenshot_tracking:
            self._screenshot_tracking[pane_id] = {
                "process_pid": pane.process.pid,
                "last_hash": None,
                "last_change": time.time(),
            }

        track = self._screenshot_tracking[pane_id]

        # Clean up tracking if process changed
        if track["process_pid"] != pane.process.pid:
            self._screenshot_tracking[pane_id] = {
                "process_pid": pane.process.pid,
                "last_hash": None,
                "last_change": time.time(),
            }
            track = self._screenshot_tracking[pane_id]

        # Check screenshot stability
        content = pane.visible_content
        content_hash = hashlib.md5(content.encode()).hexdigest()

        now = time.time()
        if content_hash != track["last_hash"]:
            # Screenshot changed
            track["last_hash"] = content_hash
            track["last_change"] = now

        # Check if screen has stabilized
        stable_for = now - track["last_change"]

        # Consider connected if screen stable for 4+ seconds
        if stable_for > 4.0:
            # Connection established - clean up tracking
            del self._screenshot_tracking[pane_id]
            return True, "connected"

        # Still connecting
        return False, "connecting"

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
        from ...popup import quick_info
        from ...utils import truncate_command

        time.sleep(0.5)

        # Use quick_info which properly handles the wait
        quick_info(
            title=pane.title or "SSH Session: Waiting for Remote Command",
            message=f"Command: {truncate_command(command)}\n\nPress Enter when command completes",
        )
