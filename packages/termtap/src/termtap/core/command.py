"""Command preparation - handles shell-specific command formatting.

PUBLIC API:
  None - all functions are internal utilities"""

import shlex
import logging

logger = logging.getLogger(__name__)


def _prepare_command(command: str, shell_type: str) -> str:
    """Prepare command for execution in given shell.

    Args:
        command: Raw command to execute
        shell_type: Shell type (bash, fish, zsh, etc)

    Returns:
        Command ready to send to tmux
    """
    # Bash-compatible shells need no modification
    if shell_type in ["bash", "sh", "dash"]:
        return command

    # For other shells, wrap in bash -c
    logger.info(f"Wrapping command for {shell_type} shell")

    # Properly quote the command for bash -c
    # This ensures the command is passed as a single argument to bash
    quoted = shlex.quote(command)
    return f"bash -c {quoted}"


def _needs_bash_wrapper(shell_type: str) -> bool:
    """Check if shell needs bash wrapper.

    Args:
        shell_type: Shell type

    Returns:
        True if commands should be wrapped in bash -c
    """
    return shell_type not in ["bash", "sh", "dash"]
