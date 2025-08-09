"""Core tmux operations - shared utilities for all tmux modules.

PUBLIC API:
  - run_tmux: Run tmux command and return result
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


def _parse_format_line(line: str, delimiter: str = ":") -> dict:
    """Parse tmux format string output into dict.

    Args:
        line: Format string line to parse.
        delimiter: Field delimiter. Defaults to ':'.
    """
    parts = line.strip().split(delimiter)
    return {str(i): part for i, part in enumerate(parts)}


def _check_tmux_available() -> bool:
    """Check if tmux is available and server is running."""
    code, _, _ = run_tmux(["info"])
    return code == 0


def _get_current_pane() -> Optional[str]:
    """Get current tmux pane ID if inside tmux."""
    if not os.environ.get("TMUX"):
        return None

    code, stdout, _ = run_tmux(["display", "-p", "#{pane_id}"])
    if code == 0:
        return stdout.strip()
    return None


def _is_current_pane(pane_id: str) -> bool:
    """Check if given pane ID is the current pane.

    Args:
        pane_id: Pane ID to check.
    """
    current = _get_current_pane()
    return current == pane_id if current else False


def _get_pane_id(session: str, window: str, pane: str) -> Optional[str]:
    """Get pane ID for a specific session:window.pane location.

    Args:
        session: Session name.
        window: Window index (as string).
        pane: Pane index (as string).
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
