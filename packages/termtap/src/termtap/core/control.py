"""Process control operations.

PUBLIC API:
  - send_interrupt: Send Ctrl+C to a session
  - send_signal: Send arbitrary signal to process
  - kill_process: Force kill a process
"""

import os
import signal
import logging

from ..tmux import send_keys, session_exists, get_pane_for_session

logger = logging.getLogger(__name__)


def send_interrupt(session: str) -> bool:
    """Send Ctrl+C to whatever is running in session.

    Args:
        session: Tmux session name

    Returns:
        True if interrupt was sent successfully
    """
    if not session_exists(session):
        logger.error(f"Session {session} does not exist")
        return False

    try:
        pane_id = get_pane_for_session(session)
        send_keys(pane_id, "\x03")  # Ctrl+C
        logger.info(f"Sent interrupt to session {session}")
        return True
    except Exception as e:
        logger.error(f"Failed to send interrupt to {session}: {e}")
        return False


def send_signal(pid: int, sig: int = signal.SIGTERM) -> bool:
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


def kill_process(pid: int, force: bool = False) -> bool:
    """Kill a process, optionally with SIGKILL.

    Args:
        pid: Process ID
        force: Use SIGKILL instead of SIGTERM

    Returns:
        True if process was killed successfully
    """
    sig = signal.SIGKILL if force else signal.SIGTERM
    return send_signal(pid, sig)
