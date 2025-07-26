"""SSH process handler with hover dialog for permission.

Internal handler class - not part of public API.
Handler for SSH sessions with safety features like confirmation dialogs.
"""

import logging
from . import ProcessHandler
from ..tree import ProcessNode

logger = logging.getLogger(__name__)


class SSHHandler(ProcessHandler):
    """Handler for SSH sessions - always asks permission before sending commands."""

    handles = ["ssh", "scp", "sftp", "rsync"]

    def can_handle(self, process: ProcessNode) -> bool:
        """Check if this is an SSH-related process."""
        result = process.name in self.handles
        if result:
            logger.info(f"SSHHandler will handle process: {process.name}")
        return result

    def is_ready(self, process: ProcessNode) -> tuple[bool, str]:
        """Check if SSH session is ready.

        SSH is a proxy - it's always ready to forward commands.
        The remote side's readiness is not visible to us.
        """
        # SSH acts as a proxy - always ready
        return True, "ssh proxy ready"

    def interrupt(self, session_id: str) -> tuple[bool, str]:
        """Interrupt SSH session.

        Sends Ctrl+C to interrupt remote command.
        Note: ~. would disconnect the session entirely.
        """
        from ...tmux import send_keys

        success = send_keys(session_id, "C-c")
        return success, "sent Ctrl+C to remote"

    # SSH-specific hooks
    def before_send(self, session_id: str, command: str) -> str | None:
        """Always show hover dialog for SSH commands.

        This provides a safety check before sending commands to remote systems.
        """
        logger.info(f"SSHHandler.before_send: Showing hover dialog for command: {command}")

        from ...hover import show_hover

        result = show_hover(session=session_id, command=command, mode="before", title="SSH Command Confirmation")

        logger.info(f"SSHHandler.before_send: Hover dialog returned: action={result.action}, choice={result.choice}")

        if result.action == "execute":
            logger.info(f"SSHHandler.before_send: Command approved, executing: {command}")
            return command
        elif result.action == "edit":
            # Could implement command editing here
            # For now, just cancel
            logger.info("SSHHandler.before_send: Edit requested but not implemented, cancelling")
            return None
        else:  # cancel, abort, etc.
            logger.info(f"SSHHandler.before_send: Command cancelled, action was: {result.action}")
            return None

    def after_send(self, session_id: str, command: str) -> None:
        """Log SSH commands for audit trail."""
        logger.info(f"SSHHandler.after_send: Command sent to {session_id}: {command}")

    def during_command(self, session_id: str, elapsed: float) -> bool:
        """Monitor SSH command execution.

        Could add features like:
        - Timeout for hung SSH connections
        - Pattern detection for errors
        - Network connectivity checks
        """
        # For now, just continue
        # Could timeout very long commands
        if elapsed > 300:  # 5 minutes
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(f"SSH command running for {elapsed:.1f}s in {session_id}")

        return True  # Continue waiting
