"""Default handler for standard processes."""

from . import ProcessHandler
from ..tree import ProcessNode, get_process_chain
from ...tmux.utils import get_pane_pid


class DefaultHandler(ProcessHandler):
    """Default handler for shells, REPLs, and standard processes."""
    
    def can_handle(self, process: ProcessNode) -> bool:
        """Handle everything (must be last in handler list)."""
        return True
    
    def is_ready(self, session_id: str) -> tuple[bool, str]:
        """Check readiness using process state."""
        # Get fresh process info
        pid = get_pane_pid(session_id)
        chain = get_process_chain(pid)
        if not chain:
            return False, "no process"
        
        # Find active process (leaf)
        active = chain[-1]
        
        # Running = busy
        if active.is_running:
            return False, f"{active.name} running"
        
        # Has children = busy
        if active.has_children:
            return False, f"{active.name} has subprocess"
        
        # Sleeping with no children - check wait channel
        if active.is_sleeping:
            # Common wait channels when ready for input
            ready_channels = {"do_select", "do_epoll_wait", "poll_schedule_timeout"}
            if active.wait_channel in ready_channels:
                return True, f"{active.name} waiting for input"
            else:
                return False, f"{active.name} sleeping ({active.wait_channel})"
        
        return False, f"{active.name} unknown state"
    
    def during_command(self, session_id: str, elapsed: float) -> bool:
        """Default during_command - no intervention."""
        return True