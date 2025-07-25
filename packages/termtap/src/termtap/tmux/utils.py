"""Tmux utilities for low-level operations.

PUBLIC API:
  - get_pane_pid: Get PID for a session's pane
  - get_pane_for_session: Get default pane for a session
"""

import os
import subprocess
from typing import List, Tuple, Optional

from ..types import Target


def _run_tmux(args: List[str]) -> Tuple[int, str, str]:
    """Run tmux command, return (returncode, stdout, stderr).

    Args:
        args: Command arguments to pass to tmux.

    Returns:
        Tuple of (returncode, stdout, stderr).
    """
    cmd = ["tmux"] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


def _parse_format_line(line: str, delimiter: str = ":") -> dict:
    """Parse tmux format string output into dict.

    Args:
        line: Format string to parse.
        delimiter: Character to split on. Defaults to ":".

    Returns:
        Dict with string indices as keys and parts as values.
    """
    parts = line.strip().split(delimiter)
    return {str(i): part for i, part in enumerate(parts)}


def _check_tmux_available() -> bool:
    """Check if tmux is available and server is running."""
    code, _, _ = _run_tmux(["info"])
    return code == 0


def _get_current_pane() -> Optional[str]:
    """Get current tmux pane if inside tmux session.

    Returns:
        Session:window.pane format (e.g., "epic-swan:0.0") or None.
    """
    if not os.environ.get("TMUX"):
        return None

    code, stdout, _ = _run_tmux(["display", "-p", "#{session_name}:#{window_index}.#{pane_index}"])
    if code == 0:
        return stdout.strip()
    return None


def _is_current_pane(target: Target) -> bool:
    """Check if given target is the current pane.

    Args:
        target: Target specification (session, pane ID, window ID, or session:window.pane).

    Returns:
        True if target matches current pane.
    """
    current = _get_current_pane()
    return current is not None and current == target


def get_pane_pid(session_id: str) -> int:
    """Get the PID of a session's active pane.
    
    Args:
        session_id: Tmux session ID
        
    Returns:
        PID of the pane process
        
    Raises:
        RuntimeError: If PID cannot be obtained
    """
    code, stdout, stderr = _run_tmux([
        "display-message", "-t", session_id, "-p", "#{pane_pid}"
    ])
    
    if code != 0:
        raise RuntimeError(f"Failed to get pane PID: {stderr}")
    
    try:
        return int(stdout.strip())
    except ValueError:
        raise RuntimeError(f"Invalid PID: {stdout}")


def get_pane_for_session(session: str) -> str:
    """Get the default pane for a session.
    
    Args:
        session: Session name
        
    Returns:
        Pane identifier in format 'session:0.0'
    """
    return f"{session}:0.0"
