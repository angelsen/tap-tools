"""DSL syntax reference screen.

PUBLIC API:
  - DslSyntaxScreen: Full DSL syntax reference with types, brackets, anchors
"""

from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from textual.app import ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Static

from ._base import TermtapScreen

__all__ = ["DslSyntaxScreen"]


def _build_types_card() -> Panel:
    """Build types × quantifiers reference table."""
    table = Table(
        show_header=True,
        header_style="bold",
        show_lines=True,
        padding=(0, 1),
        expand=True,
    )

    table.add_column("", justify="left", width=9)
    table.add_column("1", justify="center", width=6)
    table.add_column("1+", justify="center", width=6)
    table.add_column("N", justify="center", width=6)
    table.add_column("0+", justify="center", width=6)
    table.add_column("0-1", justify="center", width=6)
    table.add_column("regex", justify="left", width=20)

    table.add_row("digit #", "#", "#+", "#N", "#*", "#?", "\\d")
    table.add_row("word  w", "w", "w+", "wN", "w*", "w?", "\\w")
    table.add_row("any   .", ".", ".+", ".N", ".*", ".?", ".")
    table.add_row("space _", "_", "_+", "_N", "_*", "_?", "' '")

    return Panel(
        table,
        title="Types × Quantifiers",
        title_align="left",
        border_style="blue",
        padding=(0, 1),
    )


def _build_brackets_card() -> Panel:
    """Build brackets reference."""
    from rich.text import Text

    lines = [
        Text.assemble(("[text]", "bold cyan"), ("     literal match (brackets escaped)         → escaped", "dim")),
        Text.assemble(("[N]", "bold cyan"), ("        exact N character gap                    → .{N}", "dim")),
        Text.assemble(("[*]", "bold cyan"), ("        any gap (0+ chars)                       → .*", "dim")),
        Text.assemble(("[+]", "bold cyan"), ("        any gap (1+ chars)                       → .+", "dim")),
    ]

    return Panel(
        Group(*lines),
        title="Brackets",
        title_align="left",
        border_style="blue",
        padding=(0, 1),
    )


def _build_anchors_card() -> Panel:
    """Build anchors reference."""
    from rich.text import Text

    lines = [
        Text.assemble(("$", "bold cyan"), ("          end of line", "dim")),
        Text.assemble(("^", "bold cyan"), ("          start of line", "dim")),
    ]

    return Panel(
        Group(*lines),
        title="Anchors",
        title_align="left",
        border_style="blue",
        padding=(0, 1),
    )


class DslSyntaxScreen(TermtapScreen):
    """Full DSL syntax reference screen.

    Shows three full-width cards:
    - Types × Quantifiers (table)
    - Brackets (literal, gap)
    - Anchors (start/end)

    Press ? or Esc to close.
    """

    BINDINGS = [
        Binding("question_mark", "back", "Close"),
        Binding("escape", "back", "Back"),
    ]

    def compose(self) -> ComposeResult:
        yield Static("[bold]DSL Syntax Reference[/bold]", id="screen-title")
        yield Static(_build_types_card())
        yield Static(_build_brackets_card())
        yield Static(_build_anchors_card())
        yield Footer()

    def action_back(self) -> None:
        """Go back to pattern screen."""
        self.app.pop_screen()
