"""Pattern list screen for managing learned patterns.

PUBLIC API:
  - PatternListScreen: View and manage learned patterns
"""

from rich.markup import escape
from rich.panel import Panel
from textual.app import ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Static

from ._base import TermtapScreen
from ..widgets.fzf_selector import FzfSelector, FzfItem

__all__ = ["PatternListScreen"]


def _build_pattern_item(process: str, state: str, pattern: str, index: int) -> FzfItem:
    """Build FzfItem for a pattern.

    Args:
        process: Process name
        state: State (ready or busy)
        pattern: Pattern text (may be multi-line)
        index: Index for value

    Returns:
        FzfItem with Panel display
    """
    border_style = "green" if state == "ready" else "yellow"

    display = Panel(
        escape(pattern),
        title=f"{process}: {state}",
        title_align="left",
        border_style=border_style,
        expand=True,
    )

    # Search on process, state, and pattern content
    search_text = f"{process} {state} {pattern}"

    return FzfItem(display=display, value=str(index), search=search_text)


class PatternListScreen(TermtapScreen):
    """View and manage learned patterns.

    Displays all patterns as cards with FzfSelector filtering.
    """

    BINDINGS = [
        Binding("ctrl+d", "delete_pattern", "Delete"),
        Binding("escape", "back", "Back"),
    ]

    def __init__(self):
        super().__init__()
        self.pattern_data: list[tuple[str, str, str]] = []  # (process, state, pattern)

    def compose(self) -> ComposeResult:
        yield Static("[bold]Learned Patterns[/bold]", id="screen-title")
        yield FzfSelector(items=[], id="pattern-selector", empty_message="No patterns learned")
        yield Footer()

    def on_mount(self) -> None:
        """Fetch and display patterns when screen mounts."""
        self._load_patterns()

    def _load_patterns(self) -> None:
        """Fetch patterns from daemon and populate list."""
        result = self.rpc("get_patterns")
        patterns = result.get("patterns", {}) if result else {}

        items: list[FzfItem] = []
        self.pattern_data = []

        for process in sorted(patterns.keys()):
            states = patterns[process]
            for state in ["ready", "busy"]:
                if state not in states:
                    continue

                for pattern_dict in states[state]:
                    if isinstance(pattern_dict, dict):
                        pattern = pattern_dict.get("match", "")
                    else:
                        pattern = str(pattern_dict)

                    item = _build_pattern_item(process, state, pattern, len(self.pattern_data))
                    items.append(item)
                    self.pattern_data.append((process, state, pattern))

        selector = self.query_one("#pattern-selector", FzfSelector)
        selector.update_items(items)

    def action_delete_pattern(self) -> None:
        """Delete the selected pattern."""
        selector = self.query_one("#pattern-selector", FzfSelector)
        value = selector.get_highlighted_value()
        if value is None:
            return

        try:
            idx = int(value)
            if idx >= len(self.pattern_data):
                return

            process, state, pattern = self.pattern_data[idx]
            self.rpc("remove_pattern", {"process": process, "pattern": pattern, "state": state})
            self._load_patterns()
        except (ValueError, IndexError):
            pass

    def on_fzf_selector_selected(self, message: FzfSelector.Selected) -> None:
        """Handle pattern selection (currently just a no-op, could open edit screen)."""
        message.stop()

    def on_fzf_selector_cancelled(self, message: FzfSelector.Cancelled) -> None:
        """Handle cancel - same as back action."""
        message.stop()
        self.action_back()
