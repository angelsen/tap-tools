"""Process state detection for termtap - pane-first architecture.

PUBLIC API:
  - detect_process: Get ProcessInfo for a pane
  - detect_all_processes: Batch detection for multiple panes
  - interrupt_process: Handler-aware interrupt
  - get_handler_for_pane: Get handler for a pane's process
"""

import logging

from .tree import get_process_chain, ProcessNode, get_all_processes, build_tree_from_processes
from .handlers import get_handler
from ..tmux import get_pane_pid, send_keys, get_pane_session_window_pane
from ..config import get_config_manager
from ..types import ProcessInfo, ProcessContext, KNOWN_SHELLS

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

    # Find last shell in chain
    shell = None
    for proc in chain:
        if proc.name in KNOWN_SHELLS:
            shell = proc

    # Find first non-skipped process
    # Skip all shells and configured skip processes
    skip = KNOWN_SHELLS.union(set(skip_processes))

    process = None
    for proc in chain:
        if proc.name not in skip:
            process = proc
            break

    # If no shell found and we have a process, it's a direct-launched process
    # (e.g., tmux new-session -s foo claude)
    if not shell and process:
        # The process is running directly without a shell
        return None, process

    # If no shell found and no process, fallback to root as shell
    if not shell:
        shell = chain[0]

    return shell, process


def detect_process(pane_id: str) -> ProcessInfo:
    """Detect shell and process state for a pane.

    Args:
        pane_id: Tmux pane ID.

    Returns:
        ProcessInfo with shell, process, and state.
    """
    try:
        pid = get_pane_pid(pane_id)
        chain = get_process_chain(pid)

        if not chain:
            return ProcessInfo(shell=None, process=None, state="unknown", pane_id=pane_id)

        config_manager = get_config_manager()
        shell, process = _extract_shell_and_process(chain, config_manager.skip_processes)

        # Determine state
        if not process or process == shell:
            # At shell prompt
            return ProcessInfo(
                shell=shell.name if shell else None,
                process=None,
                state="ready",
                pane_id=pane_id,
                wait_channel=shell.wait_channel if shell else None,
            )

        # Create ProcessContext for handler
        session_window_pane = get_pane_session_window_pane(pane_id)
        ctx = ProcessContext(pane_id=pane_id, process=process, session_window_pane=session_window_pane)

        # Use handler to determine state
        handler = get_handler(ctx)
        ready, _ = handler.is_ready(ctx)

        return ProcessInfo(
            shell=shell.name if shell else None,
            process=process.name,
            state="ready" if ready else "working",
            pane_id=pane_id,
            wait_channel=process.wait_channel,
        )

    except Exception as e:
        logger.error(f"Error detecting process: {e}")
        return ProcessInfo(shell=None, process=None, state="unknown", pane_id=pane_id)


def detect_all_processes(pane_ids: list[str]) -> dict[str, ProcessInfo]:
    """Detect process info for multiple panes efficiently.

    Single /proc scan for all panes.

    Args:
        pane_ids: List of pane IDs.

    Returns:
        Dict mapping pane ID to ProcessInfo.
    """
    results = {}

    # Single scan of /proc
    all_processes = get_all_processes()
    config_manager = get_config_manager()

    for pane_id in pane_ids:
        try:
            pid = get_pane_pid(pane_id)
            tree = build_tree_from_processes(all_processes, pid)

            if not tree:
                results[pane_id] = ProcessInfo(shell=None, process=None, state="unknown", pane_id=pane_id)
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

            shell, process = _extract_shell_and_process(chain, config_manager.skip_processes)

            # Determine state
            if not process or process == shell:
                results[pane_id] = ProcessInfo(
                    shell=shell.name if shell else None,
                    process=None,
                    state="ready",
                    pane_id=pane_id,
                    wait_channel=shell.wait_channel if shell else None,
                )
            else:
                # Create ProcessContext for handler
                session_window_pane = get_pane_session_window_pane(pane_id)
                ctx = ProcessContext(pane_id=pane_id, process=process, session_window_pane=session_window_pane)

                handler = get_handler(ctx)
                ready, _ = handler.is_ready(ctx)
                results[pane_id] = ProcessInfo(
                    shell=shell.name if shell else None,
                    process=process.name,
                    state="ready" if ready else "working",
                    pane_id=pane_id,
                    wait_channel=process.wait_channel,
                )

        except Exception as e:
            logger.error(f"Error detecting {pane_id}: {e}")
            results[pane_id] = ProcessInfo(shell=None, process=None, state="unknown", pane_id=pane_id)

    return results


def get_handler_for_pane(pane_id: str, process_name: str | None = None):
    """Get handler for a pane's process.

    Args:
        pane_id: Tmux pane ID.
        process_name: Optional process name to look for. If None, uses current active process.

    Returns:
        Handler instance or None.
    """
    try:
        pid = get_pane_pid(pane_id)
        chain = get_process_chain(pid)

        if not chain:
            return None

        config_manager = get_config_manager()
        _, process = _extract_shell_and_process(chain, config_manager.skip_processes)

        # Get session:window.pane for context
        session_window_pane = get_pane_session_window_pane(pane_id)

        # If specific process requested, find it in chain
        if process_name:
            for proc in chain:
                if proc.name == process_name:
                    ctx = ProcessContext(pane_id=pane_id, process=proc, session_window_pane=session_window_pane)
                    return get_handler(ctx)
            return None

        # Otherwise use detected process
        if process:
            ctx = ProcessContext(pane_id=pane_id, process=process, session_window_pane=session_window_pane)
            return get_handler(ctx)
        return None

    except Exception as e:
        logger.error(f"Error getting handler: {e}")
        return None


def interrupt_process(pane_id: str) -> tuple[bool, str]:
    """Send interrupt to a pane using handler-specific method.

    Args:
        pane_id: Tmux pane ID.

    Returns:
        (success, message) tuple.
    """
    try:
        info = detect_process(pane_id)

        if not info.process:
            # At shell prompt - just send Ctrl+C
            success = send_keys(pane_id, "C-c", enter=False)
            return success, "sent Ctrl+C to shell"

        # Get handler for the process
        pid = get_pane_pid(pane_id)
        chain = get_process_chain(pid)
        config_manager = get_config_manager()
        _, process = _extract_shell_and_process(chain, config_manager.skip_processes)

        if process:
            # Create ProcessContext for handler
            session_window_pane = get_pane_session_window_pane(pane_id)
            ctx = ProcessContext(pane_id=pane_id, process=process, session_window_pane=session_window_pane)

            handler = get_handler(ctx)
            return handler.interrupt(ctx)
        else:
            success = send_keys(pane_id, "C-c", enter=False)
            return success, "sent Ctrl+C"

    except Exception as e:
        logger.error(f"Error interrupting {pane_id}: {e}")
        return False, f"error: {e}"
