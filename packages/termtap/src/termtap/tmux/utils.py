"""Internal tmux utilities for low-level operations.

PUBLIC API: (none)

PACKAGE API:
  - _run_tmux: Execute tmux commands and return results
  - _parse_format_line: Parse tmux format string output

PRIVATE:
  - _check_tmux_available: Check if tmux is available
  - _get_current_pane: Get current tmux pane identifier
  - _is_current_pane: Check if given pane is current
"""

import os
import subprocess
from typing import List, Tuple, Optional


def _run_tmux(args: List[str]) -> Tuple[int, str, str]:
    """Run tmux command, return (returncode, stdout, stderr)."""
    cmd = ["tmux"] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


def _parse_format_line(line: str, delimiter: str = ":") -> dict:
    """Parse tmux format string output into dict.

    Example: 'mysession:1234567:0' -> {'0': 'mysession', '1': '1234567', '2': '0'}
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
        Session:window.pane format (e.g., "epic-swan:0.0") or None
    """
    if not os.environ.get("TMUX"):
        return None

    code, stdout, _ = _run_tmux(
        ["display", "-p", "#{session_name}:#{window_index}.#{pane_index}"]
    )
    if code == 0:
        return stdout.strip()
    return None


def _is_current_pane(pane_id: str) -> bool:
    """Check if given pane_id is the current pane.

    Args:
        pane_id: Pane identifier (e.g., "epic-swan:0.0")

    Returns:
        True if pane_id matches current pane
    """
    current = _get_current_pane()
    return current is not None and current == pane_id
