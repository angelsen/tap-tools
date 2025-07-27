"""termtap ReplKit2 application - pane-first architecture."""

from dataclasses import dataclass, field

from replkit2 import App

from .core import ExecutorState


@dataclass
class TermTapState:
    """Application state for termtap pane management."""
    executor: ExecutorState = field(default_factory=ExecutorState)


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


# Import formatters and commands (triggers registration)
from . import formatters  # noqa: E402, F401
from . import commands  # noqa: E402, F401


if __name__ == "__main__":
    import sys
    if "--mcp" in sys.argv:
        app.mcp.run()
    else:
        app.run(title="termtap")