"""Process control operations.

Internal module - not part of public API.
Contains utilities for sending signals and interrupts to processes.
All functions are prefixed with underscore to indicate internal use.
"""

import os
import signal
import logging

from ..tmux import send_keys

logger = logging.getLogger(__name__)


def _send_interrupt(pane_id: str) -> bool:
    """Send Ctrl+C to whatever is running in pane.

    Args:
        pane_id: Tmux pane ID

    Returns:
        True if interrupt was sent successfully
    """
    try:
        send_keys(pane_id, "C-c")
        logger.info(f"Sent interrupt to pane {pane_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to send interrupt to {pane_id}: {e}")
        return False


def _send_signal(pid: int, sig: int = signal.SIGTERM) -> bool:
    """Send a signal to a specific process.

    Args:
        pid: Process ID
        sig: Signal number (default: SIGTERM)

    Returns:
        True if signal was sent successfully
    """
    try:
        os.kill(pid, sig)
        logger.info(f"Sent signal {sig} to PID {pid}")
        return True
    except ProcessLookupError:
        logger.error(f"Process {pid} not found")
        return False
    except PermissionError:
        logger.error(f"Permission denied to signal process {pid}")
        return False
    except Exception as e:
        logger.error(f"Failed to send signal to {pid}: {e}")
        return False


def _kill_process(pid: int, force: bool = False) -> bool:
    """Kill a process, optionally with SIGKILL.

    Args:
        pid: Process ID
        force: Use SIGKILL instead of SIGTERM

    Returns:
        True if process was killed successfully
    """
    sig = signal.SIGKILL if force else signal.SIGTERM
    return _send_signal(pid, sig)
