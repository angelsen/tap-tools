"""SSH process handler with hover dialog for permission.

PUBLIC API:
  - (none - internal module)
"""

import logging
from . import ProcessHandler
from ..tree import ProcessNode

logger = logging.getLogger(__name__)


class _SSHHandler(ProcessHandler):
    """Handler for SSH sessions - always asks permission before sending commands."""

    handles = ["ssh", "scp", "sftp", "rsync"]

    def can_handle(self, process: ProcessNode) -> bool:
        """Check if this is an SSH-related process.

        Args:
            process: The ProcessNode to check.

        Returns:
            True if process name matches SSH-related executables.
        """
        result = process.name in self.handles
        if result:
            logger.info(f"SSHHandler will handle process: {process.name}")
        return result

    def is_ready(self, process: ProcessNode) -> tuple[bool, str]:
        """Check if SSH session is ready.

        Args:
            process: The ProcessNode to check.

        Returns:
            Always (True, "ssh proxy ready") as SSH acts as a proxy.
        """
        return True, "ssh proxy ready"

    def interrupt(self, session_id: str) -> tuple[bool, str]:
        """Interrupt SSH session.

        Args:
            session_id: Tmux session ID.

        Returns:
            Tuple of (success, message) indicating result.
        """
        from ...tmux import send_keys

        success = send_keys(session_id, "C-c")
        return success, "sent Ctrl+C to remote"

    def before_send(self, session_id: str, command: str) -> str | None:
        """Always show hover dialog for SSH commands.

        Args:
            session_id: Tmux session ID.
            command: Command to be sent.

        Returns:
            Modified command or None to cancel.
        """
        logger.info(f"SSHHandler.before_send: Showing hover dialog for command: {command}")

        from ...hover import show_hover

        result = show_hover(session=session_id, command=command, mode="before", title="SSH Command Confirmation")

        logger.info(f"SSHHandler.before_send: Hover dialog returned: action={result.action}, choice={result.choice}")

        if result.action == "execute":
            logger.info(f"SSHHandler.before_send: Command approved, executing: {command}")
            return command
        elif result.action == "edit":
            logger.info("SSHHandler.before_send: Edit requested but not implemented, cancelling")
            return None
        else:
            logger.info(f"SSHHandler.before_send: Command cancelled, action was: {result.action}")
            return None

    def after_send(self, session_id: str, command: str) -> None:
        """Log SSH commands for audit trail.

        Args:
            session_id: Tmux session ID.
            command: Command that was sent.
        """
        logger.info(f"SSHHandler.after_send: Command sent to {session_id}: {command}")

    def during_command(self, session_id: str, elapsed: float) -> bool:
        """Monitor SSH command execution.

        Args:
            session_id: Tmux session ID.
            elapsed: Seconds elapsed since command started.

        Returns:
            True to continue waiting, False to stop waiting.
        """
        if elapsed > 300:
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(f"SSH command running for {elapsed:.1f}s in {session_id}")

        return True
