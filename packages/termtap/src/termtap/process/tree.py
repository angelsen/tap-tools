"""Process tree analysis and information gathering.

PUBLIC API:
  (None - all functions and classes are internal)
"""

import subprocess
from typing import List, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class _ProcessInfo:
    """Information about a process."""

    pid: int
    ppid: int
    name: str
    cmdline: str
    state: str  # R=running, S=sleeping, etc

    @property
    def is_sleeping(self) -> bool:
        """Check if process is sleeping (waiting)."""
        return self.state.startswith("S")

    @property
    def is_running(self) -> bool:
        """Check if process is actively running."""
        return self.state.startswith("R")


def _get_process_info(pid: int) -> Optional[_ProcessInfo]:
    """Get information about a specific process.

    Args:
        pid: Process ID.
    """
    try:
        # Use ps to get process info
        # Format: PID,PPID,STATE,COMMAND,ARGS
        result = subprocess.run(
            ["ps", "-o", "pid,ppid,state,comm,args", "-p", str(pid)], capture_output=True, text=True, check=True
        )

        lines = result.stdout.strip().split("\n")
        if len(lines) < 2:
            return None

        # Parse the output (skip header)
        parts = lines[1].split(None, 4)  # Split on whitespace, max 5 parts
        if len(parts) < 4:
            return None

        return _ProcessInfo(
            pid=int(parts[0]),
            ppid=int(parts[1]),
            state=parts[2],
            name=parts[3],
            cmdline=parts[4] if len(parts) > 4 else parts[3],
        )

    except (subprocess.CalledProcessError, ValueError) as e:
        logger.debug(f"Failed to get process info for PID {pid}: {e}")
        return None


def _get_process_tree(pid: int) -> List[_ProcessInfo]:
    """Get full process tree starting from a PID.

    Args:
        pid: Starting process ID.
    """
    tree = []
    current_pid = pid

    # Walk up the tree to find root
    while current_pid:
        info = _get_process_info(current_pid)
        if not info:
            break

        tree.insert(0, info)  # Insert at beginning to maintain order

        # Stop at init (PID 1) or when we reach the shell owner
        if info.ppid <= 1:
            break

        current_pid = info.ppid

    return tree


def _get_child_processes(ppid: int) -> List[_ProcessInfo]:
    """Get all direct child processes of a parent PID.

    Args:
        ppid: Parent process ID.
    """
    try:
        # Get all processes with this parent
        result = subprocess.run(
            ["ps", "--ppid", str(ppid), "-o", "pid,ppid,state,comm,args"], capture_output=True, text=True
        )

        children = []
        lines = result.stdout.strip().split("\n")

        # Skip header if present
        for line in lines[1:]:
            parts = line.split(None, 4)
            if len(parts) >= 4:
                children.append(
                    _ProcessInfo(
                        pid=int(parts[0]),
                        ppid=int(parts[1]),
                        state=parts[2],
                        name=parts[3],
                        cmdline=parts[4] if len(parts) > 4 else parts[3],
                    )
                )

        return children

    except (subprocess.CalledProcessError, ValueError) as e:
        logger.debug(f"Failed to get child processes for PID {ppid}: {e}")
        return []


def _find_shell_in_tree(tree: List[_ProcessInfo]) -> Optional[str]:
    """Find the shell type from a process tree.

    Args:
        tree: Process tree from _get_process_tree().
    """
    shells = {"bash", "fish", "zsh", "sh", "dash", "ksh", "tcsh", "csh"}

    for process in tree:
        if process.name in shells:
            return process.name

    return None
