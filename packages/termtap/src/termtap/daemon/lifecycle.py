"""Daemon lifecycle management.

PUBLIC API:
  - start_daemon: Start daemon in background
  - stop_daemon: Stop running daemon
  - daemon_status: Check daemon status
  - is_daemon_running: Quick check if daemon is alive
"""

import asyncio
import atexit
import os
import signal
import sys
import time

from ..paths import PID_PATH, SOCKET_PATH

__all__ = ["start_daemon", "stop_daemon", "daemon_status", "is_daemon_running"]


def is_daemon_running() -> bool:
    """Check if daemon is running by checking PID file and socket."""
    if not PID_PATH.exists():
        return False

    try:
        pid = int(PID_PATH.read_text().strip())
        # Check if process exists
        os.kill(pid, 0)
        # Also verify socket exists
        return SOCKET_PATH.exists()
    except (ValueError, ProcessLookupError, PermissionError):
        # Stale PID file
        _cleanup_stale()
        return False


def _cleanup_stale():
    """Clean up stale PID and socket files."""
    for path in [PID_PATH, SOCKET_PATH]:
        if path.exists():
            try:
                path.unlink()
            except OSError:
                pass


def start_daemon(foreground: bool = False) -> dict:
    """Start the daemon.

    Args:
        foreground: If True, run in foreground (blocking). If False, fork to background.

    Returns:
        {"status": "started", "pid": N} or {"status": "already_running", "pid": N}
    """
    if is_daemon_running():
        pid = int(PID_PATH.read_text().strip())
        return {"status": "already_running", "pid": pid}

    _cleanup_stale()

    if foreground:
        return _run_daemon_foreground()
    else:
        return _run_daemon_background()


def _run_daemon_foreground() -> dict:
    """Run daemon in foreground (blocking)."""
    pid = os.getpid()
    PID_PATH.write_text(str(pid))
    atexit.register(_cleanup_on_exit)

    from .server import TermtapDaemon

    daemon = TermtapDaemon()

    try:
        asyncio.run(daemon.run())
    except KeyboardInterrupt:
        pass

    return {"status": "stopped", "pid": pid}


def _run_daemon_background() -> dict:
    """Fork daemon to background."""
    # Double fork to daemonize
    pid = os.fork()
    if pid > 0:
        # Parent - wait briefly for daemon to start
        time.sleep(0.5)
        if is_daemon_running():
            daemon_pid = int(PID_PATH.read_text().strip())
            return {"status": "started", "pid": daemon_pid}
        return {"status": "failed", "error": "Daemon failed to start"}

    # Child - detach from terminal
    os.setsid()

    # Second fork
    pid = os.fork()
    if pid > 0:
        os._exit(0)

    # Grandchild - actual daemon
    # Redirect std streams
    sys.stdin = open(os.devnull, "r")
    sys.stdout = open(os.devnull, "w")
    sys.stderr = open(os.devnull, "w")

    # Write PID
    PID_PATH.write_text(str(os.getpid()))
    atexit.register(_cleanup_on_exit)

    from .server import TermtapDaemon

    daemon = TermtapDaemon()

    try:
        asyncio.run(daemon.run())
    except Exception:
        pass
    finally:
        _cleanup_on_exit()

    os._exit(0)


def _cleanup_on_exit():
    """Clean up PID file on exit."""
    try:
        if PID_PATH.exists():
            PID_PATH.unlink()
    except OSError:
        pass


def stop_daemon(timeout: float = 5.0) -> dict:
    """Stop the daemon.

    Args:
        timeout: How long to wait for graceful shutdown.

    Returns:
        {"status": "stopped"} or {"status": "not_running"} or {"status": "killed"}
    """
    if not is_daemon_running():
        return {"status": "not_running"}

    try:
        pid = int(PID_PATH.read_text().strip())
    except (ValueError, FileNotFoundError):
        return {"status": "not_running"}

    # Send SIGTERM for graceful shutdown
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        _cleanup_stale()
        return {"status": "not_running"}

    # Wait for graceful shutdown
    start = time.time()
    while time.time() - start < timeout:
        try:
            os.kill(pid, 0)
            time.sleep(0.1)
        except ProcessLookupError:
            _cleanup_stale()
            return {"status": "stopped"}

    # Force kill if still running
    try:
        os.kill(pid, signal.SIGKILL)
        time.sleep(0.1)
    except ProcessLookupError:
        pass

    _cleanup_stale()
    return {"status": "killed"}


def daemon_status() -> dict:
    """Get daemon status.

    Returns:
        {"running": bool, "pid": N or None, "socket": path or None}
    """
    running = is_daemon_running()
    pid = None

    if PID_PATH.exists():
        try:
            pid = int(PID_PATH.read_text().strip())
        except ValueError:
            pass

    return {
        "running": running,
        "pid": pid if running else None,
        "socket": str(SOCKET_PATH) if running else None,
    }
