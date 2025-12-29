"""WebTap - Chrome DevTools Protocol REPL.

PUBLIC API:
  - app: Main ReplKit2 App instance (lazy loaded)
  - main: Entry point function for CLI
  - __version__: Package version string
"""

import sys
from importlib.metadata import version

__version__ = version("webtap-tool")

# Lazy load app to avoid daemon dependency for --help/--version
_app = None


def _get_app():
    """Get the app instance, loading it lazily."""
    global _app
    if _app is None:
        import atexit
        from webtap.app import app as _loaded_app

        _app = _loaded_app
        atexit.register(lambda: _app.state.cleanup() if _app and hasattr(_app, "state") and _app.state else None)
    return _app


def __getattr__(name: str):
    """Lazy load app for backward compatibility."""
    if name == "app":
        return _get_app()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# CLI commands that need the app (typer-based)
_APP_COMMANDS = {"setup-extension", "setup-chrome", "setup-desktop", "setup-cleanup", "run-chrome", "setup-android"}

HELP_TEXT = f"""WebTap v{__version__} - Chrome DevTools Protocol debugger

USAGE:
  webtap                    Interactive REPL (default in terminal)
  webtap <command>          Run CLI command
  webtap < script.txt       MCP server mode (piped input)

COMMANDS:
  run-chrome                Launch Chrome with debugging enabled
  setup-android             Set up Android device debugging
  setup-extension           Download Chrome extension
  setup-chrome              Install Chrome wrapper script
  setup-desktop             Install desktop launcher
  setup-cleanup             Clean up old installations
  daemon [start|stop|status]  Manage background daemon
  status                    Show daemon and connection status

OPTIONS:
  --help, -h                Show this help message
  --version, -v             Show version

Use 'webtap <command> --help' for command-specific help.

REPL COMMANDS:
  connect(), pages(), network(), request(), js(), fetch(), ...
  Type 'help()' in REPL for full command list.

EXAMPLES:
  webtap run-chrome         Launch Chrome for debugging
  webtap                    Start REPL, then: connect(0)
  webtap status             Check daemon and connection state
"""


def main():
    """Entry point for WebTap."""
    arg = sys.argv[1] if len(sys.argv) > 1 else None

    # Flags (no daemon needed)
    if arg in ("--help", "-h", "help"):
        print(HELP_TEXT)
        return

    if arg in ("--version", "-v"):
        from webtap.daemon import daemon_running, get_daemon_version

        print(f"webtap {__version__}")
        if daemon_running():
            ver = get_daemon_version()
            print(f"daemon {ver}" if ver else "daemon running (version unknown)")
        else:
            print("daemon not running")
        return

    # Status command (no daemon needed)
    if arg == "status":
        from webtap.daemon import daemon_status

        status = daemon_status()
        if not status["running"]:
            print("Daemon: not running")
            if status.get("error"):
                print(f"Error: {status['error']}")
        else:
            print(f"Daemon: running (pid {status['pid']})")
            connections = status.get("connections", [])
            if status.get("connected") and connections:
                first = connections[0]
                print(f"Connected: {first.get('title', 'Unknown')}")
                print(f"URL: {first.get('url', 'Unknown')}")
                print(f"Events: {status.get('event_count', 0)}")
                if len(connections) > 1:
                    print(f"Targets: {len(connections)} connected")
                    for conn in connections:
                        print(f"  - {conn.get('target')}: {conn.get('title', 'Untitled')}")
            else:
                print("Connected: no")
        return

    # Daemon subcommand
    if arg == "daemon":
        from webtap.daemon import handle_cli

        handle_cli(sys.argv[2:])
        return

    # Internal daemon flag (used by spawning)
    if arg == "--daemon":
        from webtap.daemon import start_daemon

        start_daemon()
        return

    # App-based CLI commands
    if arg in _APP_COMMANDS:
        from webtap.daemon import ensure_daemon

        ensure_daemon()
        _get_app().cli()
        return

    # Default: REPL or MCP mode
    from webtap.daemon import ensure_daemon

    ensure_daemon()

    if sys.stdin.isatty():
        # REPL mode
        try:
            from webtap.daemon import get_daemon_url
            import httpx

            response = httpx.get(f"{get_daemon_url()}/status", timeout=1.0)
            notices = response.json().get("notices", []) if response.status_code == 200 else []
        except Exception:
            notices = []

        if notices:
            print("\n" + "=" * 60)
            print("  NOTICES")
            print("=" * 60)
            for notice in notices:
                print(f"  - {notice['message']}")
            print("=" * 60 + "\n")

        _get_app().run(title="WebTap - Chrome DevTools Protocol REPL")
    else:
        # MCP mode
        _get_app().mcp.run()


__all__ = ["main", "__version__"]
