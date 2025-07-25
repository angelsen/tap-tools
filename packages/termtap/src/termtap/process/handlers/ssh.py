"""Handler for SSH sessions."""

from typing import Optional

from . import ProcessHandler
from ..tree import ProcessNode


class SSHHandler(ProcessHandler):
    """Handler for SSH proxy sessions."""
    
    def can_handle(self, process: ProcessNode) -> bool:
        """Handle ssh, mosh, telnet."""
        return process.name in ["ssh", "mosh", "telnet"]
    
    def is_ready(self, session_id: str) -> tuple[bool, str]:
        """SSH is always ready (proxy)."""
        return True, "ssh proxy ready"
    
    def pre_send(self, session_id: str, command: str) -> Optional[str]:
        """Pre-send hook for SSH."""
        # Check for dangerous commands
        dangerous = ["rm -rf /", "dd if=/dev/zero", "mkfs"]
        if any(d in command for d in dangerous):
            # Could trigger hover dialog here
            from ...hover import show_hover
            result = show_hover(session=session_id, command=command, mode="before")
            if result.action == "cancel":
                return None  # Cancel
        
        return command
    
    def during_command(self, session_id: str, elapsed: float) -> bool:
        """SSH during_command - no intervention."""
        return True