"""Main application entry point for termtap terminal pane manager.

Provides dual REPL/MCP functionality for terminal pane management with tmux
integration. Built on ReplKit2 framework with daemon architecture.
"""

from dataclasses import dataclass

from replkit2 import App


@dataclass
class TermTapState:
    """Application state for termtap."""

    pass


# Must be created before command imports for decorator registration
app = App(
    "termtap",
    TermTapState,
    mcp_config={
        "uri_scheme": "termtap",
        "instructions": "Terminal pane manager with tmux and daemon architecture",
    },
)


# Command imports trigger @app.command decorator registration
from .commands import execute  # noqa: E402, F401
from .commands import pane  # noqa: E402, F401
from .commands import ls  # noqa: E402, F401
from .commands import interrupt  # noqa: E402, F401
from .commands import send_keystrokes  # noqa: E402, F401


def _ensure_daemon():
    """Ensure daemon is running before app starts."""
    from .daemon.lifecycle import is_daemon_running, start_daemon

    if not is_daemon_running():
        try:
            start_daemon()
        except Exception:
            pass  # Continue even if daemon fails


if __name__ == "__main__":
    import sys

    _ensure_daemon()

    if "--mcp" in sys.argv:
        app.mcp.run()
    else:
        app.run(title="termtap")
