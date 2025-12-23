"""WebTap - Chrome DevTools Protocol REPL.

Main entry point for WebTap browser debugging tool. Provides both REPL and MCP
functionality for Chrome DevTools Protocol interaction with native CDP event
storage and on-demand querying.

PUBLIC API:
  - app: Main ReplKit2 App instance
  - main: Entry point function for CLI
  - __version__: Package version string
"""

import atexit
import sys
from importlib.metadata import version

from webtap.app import app

__version__ = version("webtap-tool")

atexit.register(lambda: app.state.cleanup() if hasattr(app, "state") and app.state else None)


def _handle_daemon():
    """Handle daemon subcommand (webtap daemon start|stop|status)."""
    from webtap.daemon import start_daemon, stop_daemon, daemon_status

    action = sys.argv[2] if len(sys.argv) > 2 else "start"

    if action == "start":
        start_daemon()
    elif action == "stop":
        try:
            stop_daemon()
            print("Daemon stopped")
        except RuntimeError as e:
            print(f"Error: {e}")
            sys.exit(1)
    elif action == "status":
        status = daemon_status()
        if status["running"]:
            print(f"Daemon running (pid: {status['pid']})")
            if status.get("connected"):
                print(f"Connected to: {status.get('page_title', 'Unknown')}")
                print(f"Events: {status.get('event_count', 0)}")
            else:
                print("Not connected to any page")
        else:
            print("Daemon not running")
            if status.get("error"):
                print(f"Error: {status['error']}")
    else:
        print(f"Unknown daemon action: {action}")
        print("Usage: webtap daemon [start|stop|status]")
        sys.exit(1)


def _print_notice_banner(notices: list) -> None:
    """Print notices as a banner before REPL."""
    if not notices:
        return

    print("\n" + "=" * 60)
    print("  NOTICES")
    print("=" * 60)
    for notice in notices:
        print(f"  • {notice['message']}")
    print("=" * 60 + "\n")


def _get_daemon_notices() -> list:
    """Get notices from the daemon via health check."""
    try:
        from webtap.daemon import get_daemon_url
        import httpx

        daemon_url = get_daemon_url()
        response = httpx.get(f"{daemon_url}/status", timeout=1.0)
        if response.status_code == 200:
            status = response.json()
            return status.get("notices", [])
    except Exception:
        pass
    return []


CLI_SUBCOMMANDS = {
    "daemon": _handle_daemon,
    "setup-extension": lambda: app.cli(),
    "setup-chrome": lambda: app.cli(),
    "setup-desktop": lambda: app.cli(),
    "setup-cleanup": lambda: app.cli(),
    "run-chrome": lambda: app.cli(),
}


def main():
    """Entry point for WebTap.

    Modes are auto-detected:
    - Subcommand (e.g., `webtap daemon start`): Runs CLI command
    - Interactive terminal (TTY): Starts REPL mode
    - Pipe/redirect (no TTY): Starts MCP server mode

    The daemon is automatically started for REPL/MCP modes.
    """
    if len(sys.argv) > 1 and sys.argv[1] in CLI_SUBCOMMANDS:
        CLI_SUBCOMMANDS[sys.argv[1]]()
        return

    from webtap.daemon import ensure_daemon

    ensure_daemon()

    if sys.stdin.isatty():
        notices = _get_daemon_notices()
        _print_notice_banner(notices)
        app.run(title="WebTap - Chrome DevTools Protocol REPL")
    else:
        app.mcp.run()


__all__ = ["app", "main", "__version__"]
