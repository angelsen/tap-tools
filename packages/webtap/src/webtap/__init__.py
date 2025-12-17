"""WebTap - Chrome DevTools Protocol REPL.

Main entry point for WebTap browser debugging tool. Provides both REPL and MCP
functionality for Chrome DevTools Protocol interaction with native CDP event
storage and on-demand querying.

PUBLIC API:
  - app: Main ReplKit2 App instance
  - main: Entry point function for CLI
"""

import atexit
import sys

from webtap.app import app

# Register cleanup on exit to shutdown DB thread
atexit.register(lambda: app.state.cleanup() if hasattr(app, "state") and app.state else None)


def main():
    """Entry point for WebTap.

    Starts in one of five modes:
    - Daemon mode (with --daemon flag):
      - No args: Start daemon in foreground
      - stop: Stop running daemon
      - status: Show daemon status
    - CLI mode (with --cli flag) for command-line interface
    - MCP mode (with --mcp flag) for Model Context Protocol server
    - REPL mode (default) for interactive shell

    In REPL and MCP modes, the daemon is automatically started if not running.
    CLI mode doesn't need the daemon (only for setup commands).
    """
    # Handle daemon management
    if "--daemon" in sys.argv:
        from webtap.daemon import start_daemon, stop_daemon, daemon_status

        # Check for subcommands
        if "stop" in sys.argv:
            try:
                stop_daemon()
                print("Daemon stopped")
            except RuntimeError as e:
                print(f"Error: {e}")
                sys.exit(1)
        elif "status" in sys.argv:
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
            # Start daemon in foreground
            start_daemon()
        return

    # CLI mode doesn't need daemon
    if "--cli" in sys.argv:
        sys.argv.remove("--cli")
        app.cli()
        return

    # REPL and MCP modes need daemon
    from webtap.daemon import ensure_daemon

    ensure_daemon()

    if "--mcp" in sys.argv:
        app.mcp.run()
    else:
        # Run REPL
        app.run(title="WebTap - Chrome DevTools Protocol REPL")


__all__ = ["app", "main"]
