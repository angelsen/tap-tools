"""DSL reference widget with compact examples.

PUBLIC API:
  - DslReference: Static widget showing compact DSL pattern examples
"""

from rich.columns import Columns
from rich.panel import Panel
from rich.text import Text
from textual.widgets import Static

__all__ = ["DslReference"]


def _build_example_card(title: str, examples: list[tuple[str, str]], style: str) -> Panel:
    """Build compact example card panel.

    Args:
        title: Card title
        examples: List of (terminal_text, dsl_pattern) tuples
        style: Border style color
    """
    lines = []
    for i, (terminal, pattern) in enumerate(examples):
        if i > 0:
            lines.append(Text(""))
        lines.append(Text(terminal, style="dim"))
        lines.append(Text(pattern, style="bold cyan"))

    from rich.console import Group

    return Panel(
        Group(*lines),
        title=title,
        title_align="left",
        border_style=style,
        padding=(0, 1),
    )


class DslReference(Static):
    """Compact DSL examples (press ? for full syntax)."""

    def __init__(self):
        super().__init__("", id="dsl-reference")

    def on_mount(self) -> None:
        """Build and display reference content."""
        self._refresh_content()

    def _refresh_content(self) -> None:
        """Update displayed content with compact examples."""
        # Two examples each for Ready/Busy
        ready_examples = [
            ("$", "$"),
            ("[$ ]$", "[$ ]$"),
        ]

        busy_examples = [
            ("Serving HTTP on 0.0.0.0", "[Serving HTTP on ].+"),
            ("VITE v5.0.0 ready", "[VITE].+[ready]"),
        ]

        ready_card = _build_example_card("Ready", ready_examples, "green")
        busy_card = _build_example_card("Busy", busy_examples, "yellow")

        # Side by side cards
        cards = Columns([ready_card, busy_card], equal=True, expand=True)

        self.update(cards)
