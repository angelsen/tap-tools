"""Daemon lifecycle management for WebTap.

PUBLIC API:
  - daemon_running: Check if daemon is running
  - ensure_daemon: Spawn daemon if not running
  - start_daemon: Run daemon in foreground (--daemon flag)
  - daemon_status: Get daemon status information
  - get_daemon_version: Get version from running daemon
  - get_daemon_url: Get daemon URL for HTTP requests
  - handle_cli: Handle daemon CLI subcommand
"""

import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import httpx

from webtap.utils.ports import find_available_port

logger = logging.getLogger(__name__)

BASE_DAEMON_PORT = 37650
MAX_PORT_TRIES = 10

STATE_DIR = Path("~/.local/state/webtap").expanduser()
PIDFILE = STATE_DIR / "daemon.pid"
PORT_FILE = STATE_DIR / "daemon.port"
LOG_FILE = STATE_DIR / "daemon.log"

_cached_daemon_url: str | None = None


def _check_health(port: int) -> dict | None:
    """Check daemon health endpoint on given port.

    Args:
        port: Port number to check

    Returns:
        Health response dict if healthy, None otherwise
    """
    try:
        response = httpx.get(f"http://localhost:{port}/health", timeout=0.5)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception:
        return None


def _find_daemon_port() -> int:
    """Find an available port for the daemon."""
    port = find_available_port(start=BASE_DAEMON_PORT, max_tries=MAX_PORT_TRIES)
    if port is None:
        raise RuntimeError(
            f"No available daemon port in range {BASE_DAEMON_PORT}-{BASE_DAEMON_PORT + MAX_PORT_TRIES - 1}"
        )
    return port


def _discover_daemon_port() -> int | None:
    """Discover the daemon port from file or by scanning."""
    global _cached_daemon_url

    if _cached_daemon_url:
        port = int(_cached_daemon_url.split(":")[-1])
        if _check_health(port):
            return port
        _cached_daemon_url = None

    if PORT_FILE.exists():
        try:
            port = int(PORT_FILE.read_text().strip())
            if _check_health(port):
                _cached_daemon_url = f"http://localhost:{port}"
                return port
        except (ValueError, OSError):
            pass

    for offset in range(MAX_PORT_TRIES):
        port = BASE_DAEMON_PORT + offset
        if _check_health(port):
            _cached_daemon_url = f"http://localhost:{port}"
            return port

    return None


def get_daemon_url() -> str:
    """Get the daemon URL, discovering port if needed.

    Returns:
        Daemon URL (e.g., "http://localhost:37650")

    Raises:
        RuntimeError: If daemon is not running
    """
    global _cached_daemon_url

    if _cached_daemon_url:
        return _cached_daemon_url

    port = _discover_daemon_port()
    if port is None:
        raise RuntimeError("Daemon not found. Is it running?")

    _cached_daemon_url = f"http://localhost:{port}"
    return _cached_daemon_url


def get_daemon_version() -> str | None:
    """Get version from running daemon's /health endpoint.

    Returns:
        Version string if daemon is running and responsive, None otherwise.
    """
    port = _discover_daemon_port()
    if port is None:
        return None

    try:
        response = httpx.get(f"http://localhost:{port}/health", timeout=1.0)
        if response.status_code == 200:
            return response.json().get("version")
    except Exception:
        pass
    return None


def daemon_running() -> bool:
    """Check if daemon is running.

    Checks pidfile first, falls back to port scan for orphaned daemons.

    Returns:
        True if daemon is running and responsive, False otherwise.
    """
    if PIDFILE.exists():
        try:
            pid = int(PIDFILE.read_text().strip())
            os.kill(pid, 0)
            # Process alive, verify health endpoint
            port = _discover_daemon_port()
            if port is not None:
                return True
        except (ValueError, ProcessLookupError, OSError):
            PIDFILE.unlink(missing_ok=True)
            PORT_FILE.unlink(missing_ok=True)

    # Fallback: port scan for orphaned daemon (pidfile missing but alive)
    port = _discover_daemon_port()
    return port is not None


def _version_lt(a: str, b: str) -> bool:
    """Compare semantic versions.

    Args:
        a: First version string
        b: Second version string

    Returns:
        True if a < b, False otherwise
    """
    from packaging.version import Version

    return Version(a) < Version(b)


def ensure_daemon() -> None:
    """Spawn daemon if not running with version checking.

    Automatically restarts daemon if outdated.
    Raises error if client is outdated.

    Raises:
        RuntimeError: If daemon fails to start or client is outdated.
    """
    from webtap import __version__

    if daemon_running():
        daemon_ver = get_daemon_version()

        if daemon_ver and _version_lt(daemon_ver, __version__):
            logger.info(f"Restarting daemon: {daemon_ver} → {__version__}")
            _stop_daemon()
        elif daemon_ver and _version_lt(__version__, daemon_ver):
            raise RuntimeError(
                f"Daemon ({daemon_ver}) is newer than client ({__version__}). Please restart your webtap session."
            )
        else:
            logger.debug("Daemon already running")
            return

    logger.info("Starting daemon...")

    PIDFILE.parent.mkdir(parents=True, exist_ok=True)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(LOG_FILE, "a") as log:
        subprocess.Popen(
            [sys.executable, "-m", "webtap", "--daemon"],
            start_new_session=True,
            stdout=log,
            stderr=subprocess.STDOUT,
            close_fds=True,
        )

    for i in range(50):
        time.sleep(0.1)
        if daemon_running():
            logger.info("Daemon started successfully")
            return

    raise RuntimeError(f"Daemon failed to start. Check log: {LOG_FILE}")


def start_daemon() -> None:
    """Run daemon in foreground (--daemon flag).

    This function blocks until the daemon is shut down. It:
    1. Checks for existing daemon (pidfile OR port scan)
    2. Finds available port
    3. Creates pidfile and portfile
    4. Starts API server
    5. Cleans up on exit

    The API server initialization is handled in api.py.
    Uvicorn handles SIGINT/SIGTERM signals for graceful shutdown.
    """
    STATE_DIR.mkdir(parents=True, exist_ok=True)

    # Check for existing daemon (pidfile or port scan)
    existing_port = _discover_daemon_port()
    if existing_port:
        health = _check_health(existing_port)
        pid = health.get("pid") if health else None
        if pid:
            print(f"Daemon already running on port {existing_port} (pid {pid})")
        else:
            print(f"Daemon already running on port {existing_port}")
        sys.exit(1)

    port = _find_daemon_port()
    logger.info(f"Using port {port}")

    PIDFILE.write_text(str(os.getpid()))
    PORT_FILE.write_text(str(port))
    logger.info(f"Daemon started (pid: {os.getpid()}, port: {port})")

    try:
        from webtap.api import run_daemon_server

        run_daemon_server(port=port)
    finally:
        PIDFILE.unlink(missing_ok=True)
        PORT_FILE.unlink(missing_ok=True)
        logger.info("Daemon stopped")


def _stop_daemon() -> None:
    """Send SIGTERM to daemon."""
    pid = None

    # Try pidfile first
    if PIDFILE.exists():
        try:
            pid = int(PIDFILE.read_text().strip())
        except (ValueError, OSError):
            pass

    # Fallback: discover via health endpoint
    if pid is None:
        port = _discover_daemon_port()
        if port:
            health = _check_health(port)
            pid = health.get("pid") if health else None

    if pid is None:
        raise RuntimeError("Daemon not running")

    try:
        os.kill(pid, signal.SIGTERM)
        logger.info(f"Sent SIGTERM to daemon (pid: {pid})")

        for _ in range(30):
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
        daemon_url = get_daemon_url()
        response = httpx.get(f"{daemon_url}/status", timeout=2.0)
        status = response.json()
        status["running"] = True
        status["pid"] = pid
        return status
    except Exception as e:
        return {"running": False, "pid": pid, "error": str(e)}


def handle_cli(args: list[str]) -> None:
    """Handle daemon CLI subcommand.

    Args:
        args: Command line arguments after 'daemon'
    """
    action = args[0] if args else "start"

    if action == "start":
        start_daemon()
    elif action == "stop":
        try:
            _stop_daemon()
            print("Daemon stopped")
        except RuntimeError as e:
            print(f"Error: {e}")
            sys.exit(1)
    elif action == "status":
        status = daemon_status()
        if status["running"]:
            print(f"Daemon running (pid: {status['pid']})")
            connections = status.get("connections", [])
            if status.get("connected") and connections:
                print(f"Connected to: {connections[0].get('title', 'Unknown')}")
                print(f"Events: {status.get('event_count', 0)}")
            else:
                print("Not connected to any page")
        else:
            print("Daemon not running")
            if status.get("error"):
                print(f"Error: {status['error']}")
    else:
        print(f"Unknown action: {action}")
        print("Usage: webtap daemon [start|stop|status]")
        sys.exit(1)


__all__ = [
    "daemon_running",
    "ensure_daemon",
    "start_daemon",
    "daemon_status",
    "get_daemon_version",
    "get_daemon_url",
    "handle_cli",
]
