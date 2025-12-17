"""Daemon lifecycle management for WebTap.

PUBLIC API:
  - daemon_running: Check if daemon is running
  - ensure_daemon: Spawn daemon if not running
  - start_daemon: Run daemon in foreground (--daemon flag)
  - stop_daemon: Gracefully shut down daemon
  - daemon_status: Get daemon status information
"""

import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import httpx


logger = logging.getLogger(__name__)

PIDFILE = Path("~/.local/state/webtap/daemon.pid").expanduser()
DAEMON_URL = "http://localhost:8765"
LOG_FILE = Path("~/.local/state/webtap/daemon.log").expanduser()


def daemon_running() -> bool:
    """Check if daemon is running.

    Verifies both pidfile existence and health endpoint response.

    Returns:
        True if daemon is running and responsive, False otherwise.
    """
    if not PIDFILE.exists():
        return False

    # Check if process exists
    try:
        pid = int(PIDFILE.read_text().strip())
        os.kill(pid, 0)  # Signal 0 just checks if process exists
    except (ValueError, ProcessLookupError, OSError):
        # Stale pidfile
        PIDFILE.unlink(missing_ok=True)
        return False

    # Check if health endpoint responds
    try:
        response = httpx.get(f"{DAEMON_URL}/health", timeout=1.0)
        return response.status_code == 200
    except Exception:
        return False


def ensure_daemon() -> None:
    """Spawn daemon if not running.

    Raises:
        RuntimeError: If daemon fails to start within 5 seconds.
    """
    if daemon_running():
        logger.debug("Daemon already running")
        return

    logger.info("Starting daemon...")

    # Ensure directories exist
    PIDFILE.parent.mkdir(parents=True, exist_ok=True)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Spawn daemon process
    with open(LOG_FILE, "a") as log:
        subprocess.Popen(
            [sys.executable, "-m", "webtap", "--daemon"],
            start_new_session=True,
            stdout=log,
            stderr=subprocess.STDOUT,
            close_fds=True,
        )

    # Wait for daemon to be ready
    for i in range(50):  # 5 seconds total
        time.sleep(0.1)
        if daemon_running():
            logger.info("Daemon started successfully")
            return

    raise RuntimeError(f"Daemon failed to start. Check log: {LOG_FILE}")


def start_daemon() -> None:
    """Run daemon in foreground (--daemon flag).

    This function blocks until the daemon is shut down. It:
    1. Creates pidfile
    2. Starts API server
    3. Cleans up on exit

    The API server initialization is handled in api.py.
    Uvicorn handles SIGINT/SIGTERM signals for graceful shutdown.
    """
    # Ensure directories exist
    PIDFILE.parent.mkdir(parents=True, exist_ok=True)

    # Check if already running
    if daemon_running():
        print(f"Daemon already running (pid: {PIDFILE.read_text().strip()})")
        sys.exit(1)

    # Write pidfile
    PIDFILE.write_text(str(os.getpid()))
    logger.info(f"Daemon started (pid: {os.getpid()})")

    # Note: Don't register signal handlers here - uvicorn handles SIGINT/SIGTERM
    # and calling sys.exit() in a signal handler conflicts with uvicorn's shutdown

    try:
        # Initialize and run daemon server (blocks)
        from webtap.api import run_daemon_server

        run_daemon_server()
    finally:
        PIDFILE.unlink(missing_ok=True)
        logger.info("Daemon stopped")


def stop_daemon() -> None:
    """Send SIGTERM to daemon.

    Raises:
        RuntimeError: If daemon is not running.
    """
    if not PIDFILE.exists():
        raise RuntimeError("Daemon is not running (no pidfile)")

    try:
        pid = int(PIDFILE.read_text().strip())
        os.kill(pid, signal.SIGTERM)
        logger.info(f"Sent SIGTERM to daemon (pid: {pid})")

        # Wait for daemon to stop
        for _ in range(30):  # 3 seconds
            time.sleep(0.1)
            if not daemon_running():
                logger.info("Daemon stopped")
                return

        logger.warning("Daemon did not stop gracefully, may need manual intervention")
    except (ValueError, ProcessLookupError, OSError) as e:
        PIDFILE.unlink(missing_ok=True)
        raise RuntimeError(f"Failed to stop daemon: {e}")


def daemon_status() -> dict:
    """Get daemon status information.

    Returns:
        Dictionary with status information:
        - running: bool
        - pid: int or None
        - connected: bool
        - event_count: int
        - Other status fields from /status endpoint
    """
    if not daemon_running():
        return {"running": False, "pid": None}

    try:
        pid = int(PIDFILE.read_text().strip())
    except Exception:
        pid = None

    try:
        response = httpx.get(f"{DAEMON_URL}/status", timeout=2.0)
        status = response.json()
        status["running"] = True
        status["pid"] = pid
        return status
    except Exception as e:
        return {"running": False, "pid": pid, "error": str(e)}


__all__ = ["daemon_running", "ensure_daemon", "start_daemon", "stop_daemon", "daemon_status"]
