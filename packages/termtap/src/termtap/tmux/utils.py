"""Tmux utilities - pane-first operations.

PUBLIC API:
  - get_pane_pid: Get PID for a pane
  - resolve_target_to_pane: Resolve any target to a pane ID
  - list_all_panes: List all panes with full info
  - get_pane_info: Get detailed info for a pane
"""

import os
import subprocess
from typing import List, Tuple, Optional
from dataclasses import dataclass

from ..types import Target, SessionWindowPane, resolve_target, parse_convenience_target


@dataclass
class PaneInfo:
    """Complete information about a tmux pane."""
    pane_id: str  # %42
    session: str
    window_index: int
    window_name: str
    pane_index: int
    pane_title: str
    pane_pid: int
    is_active: bool
    is_current: bool
    swp: SessionWindowPane  # session:window.pane


def _run_tmux(args: List[str]) -> Tuple[int, str, str]:
    """Run tmux command, return (returncode, stdout, stderr)."""
    cmd = ["tmux"] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


def _parse_format_line(line: str, delimiter: str = ":") -> dict:
    """Parse tmux format string output into dict."""
    parts = line.strip().split(delimiter)
    return {str(i): part for i, part in enumerate(parts)}


def _check_tmux_available() -> bool:
    """Check if tmux is available and server is running."""
    code, _, _ = _run_tmux(["info"])
    return code == 0


def _get_current_pane() -> Optional[str]:
    """Get current tmux pane ID if inside tmux."""
    if not os.environ.get("TMUX"):
        return None

    code, stdout, _ = _run_tmux(["display", "-p", "#{pane_id}"])
    if code == 0:
        return stdout.strip()
    return None


def _is_current_pane(target: Target) -> bool:
    """Check if given target is the current pane.
    
    Args:
        target: Target specification (pane ID, session:window.pane, or session name).
        
    Returns:
        True if target matches current pane.
    """
    current_pane_id = _get_current_pane()
    if not current_pane_id:
        return False
    
    # If target is already a pane ID, compare directly
    if target.startswith('%'):
        return target == current_pane_id
    
    # Otherwise, resolve target to pane ID and compare
    try:
        pane_id, _ = resolve_target_to_pane(target)
        return pane_id == current_pane_id
    except RuntimeError:
        return False


def get_pane_pid(pane_id: str) -> int:
    """Get the PID of a pane's process.

    Args:
        pane_id: Pane identifier (e.g., "%42")

    Returns:
        PID of the pane process

    Raises:
        RuntimeError: If PID cannot be obtained
    """
    code, stdout, stderr = _run_tmux(["display-message", "-t", pane_id, "-p", "#{pane_pid}"])

    if code != 0:
        raise RuntimeError(f"Failed to get pane PID: {stderr}")

    try:
        return int(stdout.strip())
    except ValueError:
        raise RuntimeError(f"Invalid PID: {stdout}")


def resolve_target_to_pane(target: Target) -> tuple[str, SessionWindowPane]:
    """Resolve any target format to a pane ID and full identifier.
    
    Args:
        target: Any target string (pane ID, session:window.pane, or convenience)
        
    Returns:
        Tuple of (pane_id, session_window_pane)
        
    Raises:
        RuntimeError: If target cannot be resolved
    """
    target_type, value = resolve_target(target)
    
    if target_type == "pane_id":
        # Already have pane ID, need to get session:window.pane
        code, stdout, _ = _run_tmux([
            "display", "-t", value, "-p",
            "#{session_name}:#{window_index}.#{pane_index}"
        ])
        if code != 0:
            raise RuntimeError(f"Invalid pane ID: {value}")
        swp = stdout.strip()
        return (value, swp)
    
    elif target_type == "swp":
        # Have session:window.pane, need to get pane ID
        code, stdout, _ = _run_tmux(["display", "-t", value, "-p", "#{pane_id}"])
        if code != 0:
            raise RuntimeError(f"Invalid pane identifier: {value}")
        pane_id = stdout.strip()
        return (pane_id, value)
    
    else:  # convenience
        # Parse convenience format
        session, window, pane = parse_convenience_target(value)
        
        # Build tmux target
        if window is None:
            tmux_target = f"{session}:0.0"
        elif pane is None:
            tmux_target = f"{session}:{window}.0"
        else:
            tmux_target = f"{session}:{window}.{pane}"
        
        # Get pane ID
        code, stdout, _ = _run_tmux(["display", "-t", tmux_target, "-p", "#{pane_id}"])
        if code != 0:
            # Session might not exist - this is expected for new sessions
            raise RuntimeError(f"Cannot resolve target: {value}")
        
        pane_id = stdout.strip()
        return (pane_id, tmux_target)


def list_panes(all: bool = True, session: Optional[str] = None, window: Optional[str] = None) -> List[PaneInfo]:
    """List tmux panes with full information.
    
    Args:
        all: List all panes on server (default True)
        session: List panes in specific session only
        window: List panes in specific window (format: "session:window")
    
    Returns:
        List of PaneInfo objects sorted by session, window, pane
    """
    # Build command
    cmd = ["list-panes"]
    
    if window:
        # Window target like "epic-swan:0"
        cmd.extend(["-t", window])
    elif session:
        # Session target
        cmd.extend(["-t", session])
    elif all:
        # All panes
        cmd.append("-a")
    # else: current window (no flags)
    
    # Build JSON-like format for reliable parsing
    import json
    fields = {
        "pane_id": "#{pane_id}",
        "session_name": "#{session_name}", 
        "window_index": "#{window_index}",
        "window_name": "#{window_name}",
        "pane_index": "#{pane_index}",
        "pane_title": "#{pane_title}",
        "pane_pid": "#{pane_pid}",
        "pane_active": "#{pane_active}"
    }
    # Build format string that outputs JSON
    format_parts = [f'"{k}":"{v}"' for k, v in fields.items()]
    format_str = "{" + ",".join(format_parts) + "}"
    
    cmd.extend(["-F", format_str])
    
    code, stdout, _ = _run_tmux(cmd)
    if code != 0:
        return []
    
    panes = []
    current_pane_id = _get_current_pane()
    
    for line in stdout.strip().split('\n'):
        if not line:
            continue
        
        try:
            # Parse the JSON-like format
            data = json.loads(line)
            
            window_idx = int(data["window_index"])
            pane_idx = int(data["pane_index"])
            
            panes.append(PaneInfo(
                pane_id=data["pane_id"],
                session=data["session_name"],
                window_index=window_idx,
                window_name=data["window_name"] or str(window_idx),
                pane_index=pane_idx,
                pane_title=data["pane_title"],
                pane_pid=int(data["pane_pid"]),
                is_active=data["pane_active"] == "1",
                is_current=data["pane_id"] == current_pane_id,
                swp=f"{data['session_name']}:{window_idx}.{pane_idx}"
            ))
        except (json.JSONDecodeError, KeyError, ValueError):
            # Skip malformed lines
            continue
    
    # Sort by session, window, pane
    panes.sort(key=lambda p: (p.session, p.window_index, p.pane_index))
    return panes


def get_pane_info(pane_id: str) -> PaneInfo:
    """Get detailed information for a specific pane.
    
    Args:
        pane_id: Pane identifier (e.g., "%42")
        
    Returns:
        PaneInfo object
        
    Raises:
        RuntimeError: If pane doesn't exist
    """
    format_str = "#{pane_id}:#{session_name}:#{window_index}:#{window_name}:#{pane_index}:#{pane_title}:#{pane_pid}:#{pane_active}:#{pane_current}"
    
    code, stdout, stderr = _run_tmux(["display", "-t", pane_id, "-p", format_str])
    if code != 0:
        raise RuntimeError(f"Pane not found: {stderr}")
    
    parts = stdout.strip().split(':')
    if len(parts) < 9:
        raise RuntimeError(f"Invalid pane info format: {stdout}")
    
    current_pane_id = _get_current_pane()
    
    return PaneInfo(
        pane_id=parts[0],
        session=parts[1],
        window_index=int(parts[2]),
        window_name=parts[3] or str(parts[2]),
        pane_index=int(parts[4]),
        pane_title=parts[5],
        pane_pid=int(parts[6]),
        is_active=parts[7] == "1",
        is_current=parts[0] == current_pane_id,
        swp=f"{parts[1]}:{parts[2]}.{parts[4]}"
    )