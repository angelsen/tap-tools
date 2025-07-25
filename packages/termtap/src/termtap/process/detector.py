"""Process state detection for termtap.

PUBLIC API:
  - is_ready: Check if a session is ready for commands
  - wait_until_ready: Wait for a session to become ready
  - get_process_info: Get process information for debugging
"""

import logging
from typing import Dict, Any

from .tree import get_process_chain, ProcessNode
from .handlers import get_handler
from ..tmux.utils import get_pane_pid
from ..config import get_target_config

logger = logging.getLogger(__name__)


def _find_active_process(chain: list[ProcessNode], skip_processes: list[str]) -> ProcessNode | None:
    """Find the active process, skipping wrappers."""
    if not chain:
        return None
    
    # Skip processes from config
    skip = set(skip_processes)
    
    # Walk backwards from leaf
    for i in range(len(chain) - 1, -1, -1):
        if chain[i].name not in skip:
            return chain[i]
    
    # All are wrappers, return leaf
    return chain[-1]


def is_ready(session_id: str) -> tuple[bool, str]:
    """Check if a session is ready for input.
    
    Args:
        session_id: Tmux session ID
        
    Returns:
        Tuple of (is_ready, reason)
    """
    try:
        # Get process chain
        pid = get_pane_pid(session_id)
        chain = get_process_chain(pid)
        if not chain:
            return False, "no process found"
        
        # Get skip list from config
        config = get_target_config()
        
        # Find active process
        active = _find_active_process(chain, config.skip_processes)
        if not active:
            return False, "no active process"
        
        # Use handler to check readiness
        handler = get_handler(active)
        is_ready, reason = handler.is_ready(session_id)
        
        return is_ready, reason
        
    except Exception as e:
        logger.error(f"Error checking readiness: {e}")
        return False, f"error: {e}"


def wait_until_ready(session_id: str, timeout: float = 5.0) -> bool:
    """Wait for a session to become ready.
    
    Args:
        session_id: Tmux session ID
        timeout: Maximum seconds to wait
        
    Returns:
        True if became ready, False if timeout
    """
    try:
        # Get current process to find handler
        pid = get_pane_pid(session_id)
        chain = get_process_chain(pid)
        if not chain:
            return False
        
        # Get skip list from config
        config = get_target_config()
        active = _find_active_process(chain, config.skip_processes)
        if not active:
            return False
        
        # Use handler's wait method
        handler = get_handler(active)
        return handler.wait_until_ready(session_id, timeout)
        
    except Exception as e:
        logger.error(f"Error waiting for ready: {e}")
        return False


def get_process_info(session_id: str) -> Dict[str, Any]:
    """Get process information for debugging.
    
    Args:
        session_id: Tmux session ID
        
    Returns:
        Dict with process chain and active process
    """
    try:
        pid = get_pane_pid(session_id)
        chain = get_process_chain(pid)
        
        if not chain:
            return {"error": "no process found"}
        
        # Get skip list from config
        config = get_target_config()
        active = _find_active_process(chain, config.skip_processes)
        
        return {
            "pid": pid,
            "chain": [
                {
                    "name": p.name,
                    "pid": p.pid,
                    "state": p.state,
                    "cmd": p.cmdline[:50] + "..." if len(p.cmdline) > 50 else p.cmdline
                }
                for p in chain
            ],
            "active": {
                "name": active.name,
                "pid": active.pid,
                "state": active.state,
                "is_sleeping": active.is_sleeping
            } if active else None
        }
        
    except Exception as e:
        logger.error(f"Error getting process info: {e}")
        return {"error": str(e)}