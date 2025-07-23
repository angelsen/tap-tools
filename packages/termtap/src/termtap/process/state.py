"""Process state detection - checking if ready for input."""
import time
import subprocess
from typing import Optional, List
from dataclasses import dataclass
import logging

from .tree import get_process_info, get_child_processes

logger = logging.getLogger(__name__)


@dataclass
class ProcessState:
    """Detailed process state information."""
    pid: int
    state: str  # R, S, etc
    is_sleeping: bool
    is_waiting_on_stdin: bool
    open_files: List[str]
    wchan: Optional[str] = None  # Kernel wait channel
    
    @property
    def is_ready_for_input(self) -> bool:
        """Check if process is ready to receive input."""
        return self.is_sleeping and self.is_waiting_on_stdin


def check_stdin_wait(pid: int) -> bool:
    """Check if process is waiting on stdin using lsof.
    
    Args:
        pid: Process ID
        
    Returns:
        True if process has stdin open for reading
    """
    try:
        # Use lsof to check if reading from fd 0 (stdin)
        result = subprocess.run(
            ['lsof', '-p', str(pid), '-a', '-d', '0'],
            capture_output=True,
            text=True
        )
        
        # If lsof returns data, stdin is open
        if result.returncode == 0 and result.stdout.strip():
            # Check if it's in read mode
            return '0r' in result.stdout or '0u' in result.stdout
            
    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.debug(f"lsof not available or failed for PID {pid}")
        
    return False


def get_wait_channel(pid: int) -> Optional[str]:
    """Get kernel wait channel from /proc (Linux only).
    
    Args:
        pid: Process ID
        
    Returns:
        Wait channel name or None
    """
    try:
        with open(f"/proc/{pid}/wchan", 'r') as f:
            wchan = f.read().strip()
            return wchan if wchan and wchan != '0' else None
    except (IOError, OSError):
        return None


def is_ready_for_input(pid: int) -> bool:
    """Quick check if process is ready for input.
    
    Args:
        pid: Process ID
        
    Returns:
        True if process appears ready for input
    """
    info = get_process_info(pid)
    if not info:
        return False
        
    # Must be sleeping (not running)
    if not info.is_sleeping:
        return False
        
    # Check for common wait states that indicate ready for input
    wchan = get_wait_channel(pid)
    if wchan:
        # Common wait channels when waiting for input
        input_wait_channels = {
            'wait_woken',      # General wait
            'ep_poll',         # epoll wait
            'poll_schedule',   # poll wait
            'pipe_wait',       # Pipe read
            'tty_read',        # TTY read
            'n_tty_read',      # New TTY read
        }
        if any(chan in wchan for chan in input_wait_channels):
            return True
    
    # Fallback to checking stdin
    return check_stdin_wait(pid)


def get_process_state(pid: int) -> Optional[ProcessState]:
    """Get detailed process state.
    
    Args:
        pid: Process ID
        
    Returns:
        ProcessState with detailed information
    """
    info = get_process_info(pid)
    if not info:
        return None
        
    # Check stdin
    waiting_on_stdin = check_stdin_wait(pid)
    
    # Get wait channel
    wchan = get_wait_channel(pid)
    
    # Get open files (simplified)
    open_files = []
    try:
        result = subprocess.run(
            ['lsof', '-p', str(pid), '-F', 'n'],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            # Parse lsof output (each line starts with 'n')
            open_files = [line[1:] for line in result.stdout.splitlines() 
                         if line.startswith('n')]
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    
    return ProcessState(
        pid=pid,
        state=info.state,
        is_sleeping=info.is_sleeping,
        is_waiting_on_stdin=waiting_on_stdin,
        open_files=open_files[:10],  # Limit to first 10
        wchan=wchan
    )


def wait_for_ready_state(pid: int, timeout: float = 30.0, poll_interval: float = 0.1) -> bool:
    """Wait until process is ready for input.
    
    Args:
        pid: Process ID to monitor
        timeout: Maximum time to wait in seconds
        poll_interval: How often to check state
        
    Returns:
        True if process became ready, False if timeout
    """
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        if is_ready_for_input(pid):
            logger.info(f"Process {pid} is ready for input")
            return True
            
        # Also check if process still exists
        if not get_process_info(pid):
            logger.warning(f"Process {pid} no longer exists")
            return False
            
        time.sleep(poll_interval)
    
    logger.warning(f"Timeout waiting for process {pid} to be ready")
    return False


def is_repl_ready(pid: int) -> bool:
    """Special check for REPL readiness.
    
    REPLs might have special states when ready for input.
    
    Args:
        pid: Process ID
        
    Returns:
        True if REPL appears ready
    """
    info = get_process_info(pid)
    if not info:
        return False
        
    # Check if it's a known REPL
    repl_names = {'python', 'python3', 'ipython', 'node', 'irb'}
    if info.name not in repl_names:
        return is_ready_for_input(pid)  # Fallback to general check
        
    # For REPLs, also check child processes
    children = get_child_processes(pid)
    if children:
        # If REPL has active children, it's probably executing code
        return False
        
    # Otherwise use standard ready check
    return is_ready_for_input(pid)