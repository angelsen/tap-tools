"""Core tmux operations - shared utilities for all tmux modules.

PUBLIC API:
  - run_tmux: Run tmux command and return result
"""

import subprocess


def run_tmux(args: list[str], input: str | None = None) -> tuple[int, str, str]:
    """Run tmux command and return result.

    Args:
        args: Command arguments to pass to tmux.
        input: Optional text piped to stdin (e.g. for load-buffer -).

    Returns:
        Tuple of (returncode, stdout, stderr).
    """
    cmd = ["tmux"] + args
    result = subprocess.run(cmd, capture_output=True, text=True, input=input)
    return result.returncode, result.stdout, result.stderr
