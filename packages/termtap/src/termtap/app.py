"""termtap ReplKit2 application - pane-first architecture.

Main application entry point providing dual REPL/MCP functionality for terminal
pane management with tmux integration. Built on ReplKit2 framework with
pane-centric design for process-native terminal operations.
"""

from dataclasses import dataclass

from replkit2 import App


@dataclass
class TermTapState:
    """Application state for termtap pane management.

    Currently minimal state container for the pane-centric architecture.
    State is maintained through individual pane objects rather than
    centralized application state.
    """

    pass


# Must be created before command imports for decorator registration
app = App(
    "termtap",
    TermTapState,
    uri_scheme="termtap",
    fastmcp={
        "description": "Terminal pane manager with tmux",
        "tags": {"terminal", "automation", "tmux"},
    },
)


# Command imports trigger @app.command decorator registration
from .commands import bash  # noqa: E402, F401
from .commands import read  # noqa: E402, F401
from .commands import ls  # noqa: E402, F401
from .commands import interrupt  # noqa: E402, F401
from .commands import send_keys  # noqa: E402, F401
from .commands import track  # noqa: E402, F401
from .commands import run  # noqa: E402, F401


if __name__ == "__main__":
    import sys

    if "--mcp" in sys.argv:
        app.mcp.run()
    else:
        app.run(title="termtap")
