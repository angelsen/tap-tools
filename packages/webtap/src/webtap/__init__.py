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


_PROMPT_HOOK = {
    "type": "command",
    "command": "webtap prompt 2>/dev/null || true",
    "timeout": 3,
}

_STOP_HOOK = {
    "type": "command",
    "command": "webtap stop-hook 2>/dev/null || true",
    "timeout": 3,
}


def _prompt():
    """Fetch prompt context (controls + console) from daemon."""
    from webtap.daemon import daemon_running, get_daemon_url

    if not daemon_running():
        return

    try:
        import httpx

        url = get_daemon_url()
        response = httpx.get(f"{url}/prompt", timeout=2.0)
        if response.status_code == 200 and response.text:
            print(response.text)
    except Exception:
        pass


def _stop_hook():
    """Stop hook: check for new console errors after Claude finishes."""
    import json

    # Read hook input from stdin
    try:
        hook_input = json.load(sys.stdin)
    except Exception:
        return

    # Prevent infinite loops
    if hook_input.get("stop_hook_active"):
        return

    from webtap.daemon import daemon_running, get_daemon_url

    if not daemon_running():
        return

    try:
        import httpx

        url = get_daemon_url()
        response = httpx.get(f"{url}/console-check", timeout=2.0)
        if response.status_code == 200 and response.text:
            print(response.text)
    except Exception:
        pass


def _hooks_setup():
    """Install Claude Code hooks for controls + console integration."""
    import json
    from pathlib import Path

    settings_path = Path(".claude/settings.local.json")

    # Load existing settings or start fresh
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text())
        except json.JSONDecodeError:
            print(f"Error: {settings_path} contains invalid JSON")
            return
    else:
        settings = {}

    hooks = settings.setdefault("hooks", {})
    changed = False

    # UserPromptSubmit hook (prompt context)
    prompt_matchers = hooks.setdefault("UserPromptSubmit", [])
    has_prompt = any("webtap prompt" in h.get("command", "") for m in prompt_matchers for h in m.get("hooks", []))
    if not has_prompt:
        prompt_matchers.append({"hooks": [_PROMPT_HOOK]})
        changed = True

    # Stop hook (console error check)
    stop_matchers = hooks.setdefault("Stop", [])
    has_stop = any("webtap stop-hook" in h.get("command", "") for m in stop_matchers for h in m.get("hooks", []))
    if not has_stop:
        stop_matchers.append({"hooks": [_STOP_HOOK]})
        changed = True

    if not changed:
        print(f"Hooks already installed in {settings_path}")
        return

    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(settings, indent=2) + "\n")
    print(f"Installed hooks in {settings_path}")
    print("  UserPromptSubmit: controls + console context on each prompt")
    print("  Stop: check for new console errors after Claude finishes")


def __getattr__(name: str):
    """Lazy load app for backward compatibility."""
    if name == "app":
        return _get_app()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# CLI commands that need the app (typer-based)
_APP_COMMANDS = {"install-extension", "setup-browser", "cleanup", "run-browser", "debug-android"}

HELP_TEXT = f"""WebTap v{__version__} - Chrome DevTools Protocol debugger

USAGE:
  webtap                    Interactive REPL (default in terminal)
  webtap <command>          Run CLI command
  webtap < script.txt       MCP server mode (piped input)

COMMANDS:
  run-browser [--browser]   Launch browser with debugging (temp profile)
  setup-browser [--browser] Install wrapper + desktop launcher
  debug-android             Forward Android Chrome for debugging
  install-extension [path]  Install Chrome extension
  cleanup                   Clean up old installations
  daemon [start|stop|status]  Manage background daemon
  status                    Show daemon and connection status
  prompt                    Output prompt context (controls + console) for LLM
  hooks-setup               Install Claude Code hooks (prompt + stop)

OPTIONS:
  --help, -h                Show this help message
  --version, -v             Show version

Use 'webtap <command> --help' for command-specific help.

REPL COMMANDS:
  watch(), targets(), network(), request(), js(), fetch(), ...
  Type 'help()' in REPL for full command list.

EXAMPLES:
  webtap run-browser        Launch browser for debugging
  webtap                    Start REPL, then: watch(["9222:ABC123"])
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

    # Prompt subcommand — output controls + console context for LLM
    if arg == "prompt":
        _prompt()
        return

    # Stop hook subcommand — check for new console errors
    if arg == "stop-hook":
        _stop_hook()
        return

    # Hooks setup subcommand
    if arg == "hooks-setup":
        _hooks_setup()
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
