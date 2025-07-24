"""Shell and program detection for termtap.

PUBLIC API:
  - get_process_context: Get complete process context with shell and state info
  - ProcessContext: Process context data class
"""

from typing import Optional
from dataclasses import dataclass
import logging

from .tree import _get_process_tree, _get_process_info, _find_shell_in_tree, _ProcessInfo

logger = logging.getLogger(__name__)


@dataclass
class ProcessContext:
    """Complete context about a process and its environment.

    Attributes:
        pid: Process ID.
        shell_type: Detected shell type (bash, fish, zsh, etc).
        current_program: Currently running program name.
        process_tree: List of _ProcessInfo from root to current process.
        working_directory: Current working directory if available.
    """

    pid: int
    shell_type: str
    current_program: str
    process_tree: list[_ProcessInfo]
    working_directory: Optional[str] = None

    @property
    def is_repl(self) -> bool:
        """Check if current program is a REPL.

        Returns:
            True if current program is a known REPL.
        """
        repl_programs = {"python", "python3", "ipython", "node", "irb", "ghci"}
        return self.current_program in repl_programs

    @property
    def needs_bash_wrapper(self) -> bool:
        """Check if commands need to be wrapped in bash -c.

        Returns:
            True if shell is not bash-compatible and needs wrapping.
        """
        bash_compatible = {"bash", "sh", "dash"}
        return self.shell_type not in bash_compatible


def _detect_shell(pid: int) -> Optional[str]:
    """Detect the shell type for a process.

    Args:
        pid: Process ID (usually from tmux pane).

    Returns:
        Shell name (bash, fish, zsh, etc) or None.
    """
    tree = _get_process_tree(pid)
    if not tree:
        logger.warning(f"No process tree found for PID {pid}")
        return None

    shell = _find_shell_in_tree(tree)
    if shell:
        logger.info(f"Detected shell: {shell} for PID {pid}")
    else:
        logger.warning(f"No shell found in process tree for PID {pid}")

    return shell


def _get_current_program(pid: int) -> Optional[str]:
    """Get the currently running program.

    Args:
        pid: Process ID.
    """
    info = _get_process_info(pid)
    if info:
        return info.name
    return None


def get_process_context(pid: int) -> Optional[ProcessContext]:
    """Get complete process context.

    Args:
        pid: Process ID.

    Returns:
        ProcessContext with full information or None if process not found.
    """
    tree = _get_process_tree(pid)
    if not tree:
        return None

    # Get shell from tree
    shell = _find_shell_in_tree(tree) or "unknown"

    # Current program is the leaf (last in tree)
    current = tree[-1].name if tree else "unknown"

    # Try to get working directory from /proc
    cwd = None
    try:
        import os

        cwd = os.readlink(f"/proc/{pid}/cwd")
    except (OSError, IOError):
        logger.debug(f"Could not read cwd for PID {pid}")

    return ProcessContext(pid=pid, shell_type=shell, current_program=current, process_tree=tree, working_directory=cwd)


def _detect_shell_from_pane(pane_id: str) -> Optional[str]:
    """Detect shell type from a tmux pane.

    Args:
        pane_id: Tmux pane identifier.
    """
    # Get PID from tmux
    from ..tmux.utils import _run_tmux

    code, stdout, _ = _run_tmux(["display", "-p", "-t", pane_id, "#{pane_pid}"])

    if code != 0 or not stdout.strip():
        logger.error(f"Failed to get PID for pane {pane_id}")
        return None

    try:
        pid = int(stdout.strip())
        return _detect_shell(pid)
    except ValueError:
        logger.error(f"Invalid PID from tmux: {stdout}")
        return None
