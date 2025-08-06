"""Core tmux operations - shared utilities for all tmux modules.

PUBLIC API:
  - run_tmux: Execute tmux command and return result
  - parse_format_line: Parse tmux format string output into dict
  - check_tmux_available: Check if tmux is available and server running
"""

import os
import subprocess
from typing import Optional, Tuple, List


def run_tmux(args: List[str]) -> Tuple[int, str, str]:
    """Run tmux command and return result.

    Args:
        args: Command arguments to pass to tmux.

    Returns:
        Tuple of (returncode, stdout, stderr).
    """
    cmd = ["tmux"] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


def parse_format_line(line: str, delimiter: str = ":") -> dict:
    """Parse tmux format string output into dict.

    Args:
        line: Format string line to parse.
        delimiter: Field delimiter. Defaults to ':'.

    Returns:
        Dictionary with numbered keys for each field.
    """
    parts = line.strip().split(delimiter)
    return {str(i): part for i, part in enumerate(parts)}


def check_tmux_available() -> bool:
    """Check if tmux is available and server is running.

    Returns:
        True if tmux server is available.
    """
    code, _, _ = run_tmux(["info"])
    return code == 0


def get_current_pane() -> Optional[str]:
    """Get current tmux pane ID if inside tmux.

    Returns:
        Current pane ID if inside tmux, None otherwise.
    """
    if not os.environ.get("TMUX"):
        return None

    code, stdout, _ = run_tmux(["display", "-p", "#{pane_id}"])
    if code == 0:
        return stdout.strip()
    return None


def is_current_pane(pane_id: str) -> bool:
    """Check if given pane ID is the current pane.

    Args:
        pane_id: Pane ID to check.

    Returns:
        True if pane_id matches current pane.
    """
    current = get_current_pane()
    return current == pane_id if current else False


def get_pane_id(session: str, window: str, pane: str) -> Optional[str]:
    """Get pane ID for a specific session:window.pane location.

    Uses filtering for exact pane matching.

    Args:
        session: Session name.
        window: Window index (as string).
        pane: Pane index (as string).

    Returns:
        Pane ID if found, None otherwise.
    """
    swp = f"{session}:{window}.{pane}"
    code, stdout, _ = run_tmux(
        [
            "list-panes",
            "-t",
            swp,
            "-f",
            f"#{{==:#{{window_index}}.#{{pane_index}},{window}.{pane}}}",
            "-F",
            "#{pane_id}",
        ]
    )
    if code == 0 and stdout.strip():
        return stdout.strip()
    return None
