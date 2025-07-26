"""Process state detection for termtap.

PUBLIC API:
  - detect_process: Get ProcessInfo for a session
  - detect_all_processes: Batch detection for multiple sessions
  - interrupt_process: Handler-aware interrupt
  - get_handler_for_session: Get handler for a session's process
"""

import logging

from .tree import get_process_chain, ProcessNode, get_all_processes, build_tree_from_processes
from .handlers import get_handler
from ..tmux.utils import get_pane_pid
from ..tmux import send_keys
from ..config import get_target_config
from ..types import ProcessInfo

logger = logging.getLogger(__name__)


def _extract_shell_and_process(
    chain: list[ProcessNode], skip_processes: list[str]
) -> tuple[ProcessNode | None, ProcessNode | None]:
    """Extract shell and active process from chain.

    Args:
        chain: Process chain from root to leaf.
        skip_processes: Process names to skip when finding active process.

    Returns:
        (shell, process) where shell is the last shell in chain,
        process is first non-shell or None if at shell prompt.
    """
    if not chain:
        return None, None

    shells = {"bash", "sh", "zsh", "fish", "dash", "tcsh", "csh"}
    skip = shells.union(set(skip_processes))

    # Find last shell in chain
    shell = None
    for proc in chain:
        if proc.name in shells:
            shell = proc

    # If no shell found, root is the shell
    if not shell:
        shell = chain[0]

    # Find first non-skipped process
    process = None
    for proc in chain:
        if proc.name not in skip:
            process = proc
            break

    return shell, process


def detect_process(session_id: str) -> ProcessInfo:
    """Detect shell and process state for a session.

    Args:
        session_id: Tmux session ID.

    Returns:
        ProcessInfo with shell, process, and state.
    """
    try:
        pid = get_pane_pid(session_id)
        chain = get_process_chain(pid)

        if not chain:
            return ProcessInfo(shell="unknown", process=None, state="unknown")

        config = get_target_config()
        shell, process = _extract_shell_and_process(chain, config.skip_processes)

        # Determine state
        if not process or process == shell:
            # At shell prompt
            return ProcessInfo(shell=shell.name if shell else "unknown", process=None, state="ready")

        # Use handler to determine state
        handler = get_handler(process)
        ready, _ = handler.is_ready(process)

        return ProcessInfo(
            shell=shell.name if shell else "unknown", process=process.name, state="ready" if ready else "working"
        )

    except Exception as e:
        logger.error(f"Error detecting process: {e}")
        return ProcessInfo(shell="unknown", process=None, state="unknown")


def detect_all_processes(session_names: list[str]) -> dict[str, ProcessInfo]:
    """Detect process info for multiple sessions efficiently.

    Single /proc scan for all sessions.

    Args:
        session_names: List of session names.

    Returns:
        Dict mapping session name to ProcessInfo.
    """
    results = {}

    # Single scan of /proc
    all_processes = get_all_processes()
    config = get_target_config()

    for session in session_names:
        try:
            pid = get_pane_pid(session)
            tree = build_tree_from_processes(all_processes, pid)

            if not tree:
                results[session] = ProcessInfo(shell="unknown", process=None, state="unknown")
                continue

            # Build chain from tree
            chain = []
            current = tree
            visited = set()
            while current and current.pid not in visited:
                visited.add(current.pid)
                chain.append(current)
                if current.children:
                    current = current.children[0]
                else:
                    break

            shell, process = _extract_shell_and_process(chain, config.skip_processes)

            # Determine state
            if not process or process == shell:
                results[session] = ProcessInfo(shell=shell.name if shell else "unknown", process=None, state="ready")
            else:
                handler = get_handler(process)
                ready, _ = handler.is_ready(process)
                results[session] = ProcessInfo(
                    shell=shell.name if shell else "unknown",
                    process=process.name,
                    state="ready" if ready else "working",
                )

        except Exception as e:
            logger.error(f"Error detecting {session}: {e}")
            results[session] = ProcessInfo(shell="unknown", process=None, state="unknown")

    return results


def get_handler_for_session(session_id: str, process_name: str | None = None):
    """Get handler for a session's process.

    Args:
        session_id: Tmux session ID.
        process_name: Optional process name to look for. If None, uses current active process.

    Returns:
        Handler instance or None.
    """
    try:
        pid = get_pane_pid(session_id)
        chain = get_process_chain(pid)

        if not chain:
            return None

        config = get_target_config()
        _, process = _extract_shell_and_process(chain, config.skip_processes)

        if process_name:
            # Look for specific process
            for node in chain:
                if node.name == process_name:
                    return get_handler(node)
            return None
        else:
            # Use active process
            if process:
                return get_handler(process)
            return None

    except Exception as e:
        logger.error(f"Error getting handler: {e}")
        return None


def interrupt_process(session_id: str) -> tuple[bool, str]:
    """Send interrupt to a session using handler-specific method.

    Args:
        session_id: Tmux session ID.

    Returns:
        (success, message) tuple.
    """
    try:
        info = detect_process(session_id)

        if not info.process:
            # At shell prompt - just send Ctrl+C
            success = send_keys(session_id, "C-c")
            return success, "sent Ctrl+C to shell"

        # Get handler for the process
        pid = get_pane_pid(session_id)
        chain = get_process_chain(pid)
        config = get_target_config()
        _, process = _extract_shell_and_process(chain, config.skip_processes)

        if process:
            handler = get_handler(process)
            return handler.interrupt(session_id)
        else:
            success = send_keys(session_id, "C-c")
            return success, "sent Ctrl+C"

    except Exception as e:
        logger.error(f"Error interrupting {session_id}: {e}")
        return False, f"error: {e}"
