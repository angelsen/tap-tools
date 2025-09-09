"""SSH handler with connection detection and command confirmation.

# to_agent: Required per handlers/README.md
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
    """SSH client handler with connection detection and command confirmation.

    Provides connection state detection and interactive command confirmation
    popups for remote command execution safety.
    """

    _handles = ["ssh"]

    _screenshot_tracking = {}

    def can_handle(self, pane: Pane) -> bool:
        """Check if this handler manages SSH processes."""
        return bool(pane.process and pane.process.name in self._handles)

    def _get_process_age(self, pid: int) -> float:
        """Get process age in seconds from /proc.

        Args:
            pid: Process ID to check.
        """
        try:
            with open(f"/proc/{pid}/stat", "r") as f:
                stat = f.read()
            fields = stat[stat.rfind(")") + 1 :].strip().split()
            if len(fields) < 20:
                return 0.0

            starttime_ticks = int(fields[19])

            hz = os.sysconf(os.sysconf_names.get("SC_CLK_TCK", 2))
            with open("/proc/uptime", "r") as f:
                uptime = float(f.read().split()[0])

            process_uptime = starttime_ticks / hz
            age = uptime - process_uptime
            return age
        except (IOError, OSError, ValueError, IndexError):
            return 0.0

    def is_ready(self, pane: Pane) -> tuple[bool | None, str]:
        """Check if SSH connection is established using screenshot stability.

        Args:
            pane: Pane with SSH process information.
        """
        if not pane.process:
            return True, "no_process"

        process_age = self._get_process_age(pane.process.pid)
        if process_age > 5.0:
            if pane.pane_id in self._screenshot_tracking:
                del self._screenshot_tracking[pane.pane_id]
            return True, "connected"
        pane_id = pane.pane_id
        if pane_id not in self._screenshot_tracking:
            self._screenshot_tracking[pane_id] = {
                "process_pid": pane.process.pid,
                "last_hash": None,
                "last_change": time.time(),
            }

        track = self._screenshot_tracking[pane_id]

        # Process changed, reset tracking data
        if track["process_pid"] != pane.process.pid:
            self._screenshot_tracking[pane_id] = {
                "process_pid": pane.process.pid,
                "last_hash": None,
                "last_change": time.time(),
            }
            track = self._screenshot_tracking[pane_id]

        content = pane.visible_content
        content_hash = hashlib.md5(content.encode()).hexdigest()

        now = time.time()
        if content_hash != track["last_hash"]:
            track["last_hash"] = content_hash
            track["last_change"] = now
        stable_for = now - track["last_change"]

        if stable_for > 4.0:
            del self._screenshot_tracking[pane_id]
            return True, "connected"
        return False, "connecting"

    def _before_send_impl(self, pane: Pane, command: str) -> str | None:
        """Show edit popup for SSH commands.

        Args:
            pane: Target pane.
            command: Command to be sent.
        """
        from ...utils import truncate_command
        from tmux_popup import Popup, Canvas, Markdown, Input

        popup = Popup(width="65")
        canvas = Canvas()
        canvas.add(
            Markdown(f"""# Remote Command Execution

**Command:** {truncate_command(command)}

Edit the command or press Enter to execute as-is""")
        )
        popup.add(canvas)

        edited = popup.add(Input(placeholder="Press Enter to execute or ESC to cancel", value=command)).show()

        return edited if edited else None

    def _after_send_impl(self, pane: Pane, command: str) -> None:
        """Wait for user to indicate when remote command is done.

        Args:
            pane: Target pane.
            command: Command that was sent.
        """
        from ...utils import truncate_command
        from tmux_popup import Popup, Canvas, Markdown, Input

        time.sleep(0.5)

        popup = Popup(width="65")
        canvas = Canvas()
        canvas.add(
            Markdown(f"""# Waiting for Command Completion

**Command:** {truncate_command(command)}

The command has been sent to the remote host.
Press Enter when the command has completed.""")
        )
        popup.add(canvas)

        # Use Input with empty prompt to wait for Enter key
        popup.add(Input(prompt="", placeholder="Press Enter to continue...")).show()

    def _apply_filters(self, raw_output: str) -> str:
        """Apply aggressive filtering for SSH output.

        Args:
            raw_output: Raw captured output.
        """
        from ...filters import strip_trailing_empty_lines, collapse_empty_lines

        output = strip_trailing_empty_lines(raw_output)
        output = collapse_empty_lines(output, threshold=3)
        return output
