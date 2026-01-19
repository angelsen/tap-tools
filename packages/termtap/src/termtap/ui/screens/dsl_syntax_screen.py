"""DSL syntax reference screen.

PUBLIC API:
  - DslSyntaxScreen: Full DSL syntax reference with types, brackets, anchors
"""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Footer, Static

from ._base import TermtapScreen
from ..widgets.cards import example_card

__all__ = ["DslSyntaxScreen"]


# Content constants for cards
TYPES_CONTENT = r"""[bold]       1    1+   N    0+   0-1  regex[/]
[dim]digit #[/] #    #+   #N   #*   #?   \d
[dim]word  w[/] w    w+   wN   w*   w?   \w
[dim]any   .[/] .    .+   .N   .*   .?   .
[dim]space _[/] _    _+   _N   _*   _?   ' '"""

BRACKETS_CONTENT = r"""[bold cyan]\[text][/]     literal match (brackets escaped)         → escaped
[bold cyan]\[N][/]        exact N character gap                    → .{N}
[bold cyan]\[*][/]        any gap (0+ chars)                       → .*
[bold cyan]\[+][/]        any gap (1+ chars)                       → .+"""

ANCHORS_CONTENT = """[bold cyan]$[/]          end of line
[bold cyan]^[/]          start of line"""


class DslSyntaxScreen(TermtapScreen):
    """Full DSL syntax reference screen.

    Shows three full-width cards:
    - Types × Quantifiers (table)
    - Brackets (literal, gap)
    - Anchors (start/end)

    Press ? or Esc to close.
    """

    BINDINGS = [
        Binding("question_mark", "back", "Close", key_display="?"),
        ("escape", "back"),
    ]

    def compose(self) -> ComposeResult:
        # Content layer - all screen content
        with Vertical(classes="content-panel"):
            yield Static("[bold]DSL Syntax Reference[/bold]", classes="screen-title")
            yield example_card("Types × Quantifiers", TYPES_CONTENT, "card-info")
            yield example_card("Brackets", BRACKETS_CONTENT, "card-info")
            yield example_card("Anchors", ANCHORS_CONTENT, "card-info")
            yield Footer()

    def action_back(self) -> None:
        """Go back to pattern screen."""
        self.app.pop_screen()
