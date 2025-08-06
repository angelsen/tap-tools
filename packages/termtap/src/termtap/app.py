"""termtap ReplKit2 application - pane-first architecture."""

from dataclasses import dataclass

from replkit2 import App


@dataclass
class TermTapState:
    """Application state for termtap pane management."""
    pass


# Create the app (must be created before command imports)
app = App(
    "termtap",
    TermTapState,
    uri_scheme="bash",
    fastmcp={
        "name": "termtap",
        "description": "Terminal pane manager with tmux",
        "tags": {"terminal", "automation", "tmux"},
    },
)


# Import individual command modules (triggers registration via @app.command decorators)
from .commands import bash       # noqa: E402, F401
from .commands import read       # noqa: E402, F401
from .commands import ls         # noqa: E402, F401
from .commands import interrupt  # noqa: E402, F401
from .commands import send_keys  # noqa: E402, F401
from .commands import track      # noqa: E402, F401
from .commands import run        # noqa: E402, F401


if __name__ == "__main__":
    import sys

    if "--mcp" in sys.argv:
        app.mcp.run()
    else:
        app.run(title="termtap")
