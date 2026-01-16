"""Termtap - Terminal pane manager with daemon architecture.

A daemon-based tmux pane manager that learns process patterns from user feedback.
Built on ReplKit2 for REPL/MCP functionality.

PUBLIC API:
  - app: ReplKit2 application instance with termtap commands
  - main: Entry point for CLI
"""

import sys

__version__ = "0.11.0"
__all__ = ["main"]


def main():
    """Run termtap CLI.

    Commands:
    - termtap daemon start|stop|status
    - termtap companion [--popup|--master]
    - termtap repl
    - termtap (auto-detect: companion if tty, MCP if piped)
    """
    args = sys.argv[1:]

    if args and args[0] == "daemon":
        _handle_daemon_command(args[1:])
        return

    if args and args[0] == "companion":
        _handle_companion_command(args[1:])
        return

    if args and args[0] == "repl":
        _ensure_daemon_running()
        from .app import app

        app.run(title="termtap - Terminal Pane Manager")
        return

    _ensure_daemon_running()

    if sys.stdin.isatty():
        _handle_companion_command([])
    else:
        from .app import app

        app.mcp.run()


def _handle_daemon_command(args: list[str]):
    """Handle daemon subcommands."""
    from .daemon.lifecycle import start_daemon, stop_daemon, daemon_status

    if not args or args[0] == "status":
        status = daemon_status()
        if status["running"]:
            print(f"Daemon running (PID: {status['pid']})")
            print(f"Socket: {status['socket']}")
        else:
            print("Daemon not running")
        return

    if args[0] == "start":
        foreground = "--foreground" in args or "-f" in args
        result = start_daemon(foreground=foreground)
        if result["status"] == "already_running":
            print(f"Daemon already running (PID: {result['pid']})")
        elif result["status"] == "started":
            print(f"Daemon started (PID: {result['pid']})")
        elif result["status"] == "stopped":
            print("Daemon stopped")
        else:
            print(f"Failed to start daemon: {result.get('error', 'unknown')}")
        return

    if args[0] == "stop":
        result = stop_daemon()
        if result["status"] == "stopped":
            print("Daemon stopped")
        elif result["status"] == "killed":
            print("Daemon killed (forced)")
        elif result["status"] == "not_running":
            print("Daemon not running")
        return

    print(f"Unknown daemon command: {args[0]}")
    print("Usage: termtap daemon [start|stop|status]")


def _handle_companion_command(args: list[str]):
    """Handle companion subcommand."""
    from .ui.companion import run_companion

    popup_mode = "--popup" in args
    master_mode = "--master" in args

    run_companion(popup_mode=popup_mode, master_mode=master_mode)


def _ensure_daemon_running():
    """Ensure daemon is running before REPL/MCP commands.

    Per requirement: start daemon if not running, no-op if running, log warning if failed.
    """
    from .daemon.lifecycle import start_daemon

    try:
        result = start_daemon()
        # Success cases: "started" or "already_running"
        # Failed case: "failed" with error
        if result.get("status") == "failed":
            print(f"Warning: Failed to start daemon: {result.get('error', 'unknown')}", file=sys.stderr)
    except Exception as e:
        print(f"Warning: Failed to start daemon: {e}", file=sys.stderr)
