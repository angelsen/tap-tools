"""Pattern list screen for managing learned patterns.

PUBLIC API:
  - PatternListScreen: View and manage learned patterns
"""

from rich.console import Group
from rich.panel import Panel
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Footer, Static

from ._base import TermtapScreen
from ..widgets.fzf_selector import FzfSelector, FzfItem

__all__ = ["PatternListScreen"]


def _build_pattern_item(process: str, state: str, pattern: str, index: int, theme_vars: dict[str, str]) -> FzfItem:
    """Build FzfItem for a standalone pattern with theme-aware Rich Panel.

    Args:
        process: Process name
        state: State (ready or busy)
        pattern: Pattern text (may be multi-line)
        index: Index for value
        theme_vars: Theme CSS variables (hex color strings)

    Returns:
        FzfItem with Rich Panel using theme colors
    """
    # Use theme colors for borders
    border_color = theme_vars.get("success", "#8AD4A1") if state == "ready" else theme_vars.get("warning", "#FFC473")

    title = Text(f"{process}: {state}", style="bold")
    content = Text(pattern)  # No escape needed - Text() is literal

    display = Panel(Group(title, content), border_style=border_color, padding=(0, 1))

    # Search on process, state, and pattern content
    search_text = f"{process} {state} {pattern}"

    return FzfItem(display=display, value=str(index), search=search_text)


def _build_pair_item(process: str, ready: str, busy: str, index: int, theme_vars: dict[str, str]) -> FzfItem:
    """Build FzfItem for a pattern pair with theme-aware Rich Panel.

    Args:
        process: Process name
        ready: Ready pattern DSL
        busy: Busy pattern DSL
        index: Index for value
        theme_vars: Theme CSS variables (hex color strings)

    Returns:
        FzfItem with Rich Panel using theme colors
    """
    title = Text(f"{process}: Pair", style="bold")

    # Build content with theme colors - no escape needed for Text()
    ready_line = Text("Ready: ", style=f"bold {theme_vars.get('success', '#8AD4A1')}")
    ready_line.append(ready)  # Text.append() is literal

    busy_line = Text("Busy:  ", style=f"bold {theme_vars.get('warning', '#FFC473')}")
    busy_line.append(busy)  # Text.append() is literal

    display = Panel(
        Group(title, ready_line, busy_line), border_style=theme_vars.get("primary", "#0178D4"), padding=(0, 1)
    )

    # Search on process and both patterns
    search_text = f"{process} pair {ready} {busy}"

    return FzfItem(display=display, value=str(index), search=search_text)


class PatternListScreen(TermtapScreen):
    """View and manage learned patterns.

    Displays all patterns as cards with FzfSelector filtering.
    Enter to edit is handled via FzfSelector.Selected message.
    """

    BINDINGS = [
        ("delete", "delete_pattern", "Delete"),
        ("escape", "back", "Back"),
    ]

    def __init__(self):
        super().__init__()
        # (process, type, data) where:
        # - type="standalone": data=(state, pattern)
        # - type="pair": data=(ready, busy)
        self.pattern_data: list[tuple[str, str, tuple[str, str]]] = []

    def compose(self) -> ComposeResult:
        # Content layer - all screen content
        with Vertical(classes="content-panel"):
            yield Static("[bold]Learned Patterns[/bold]", classes="screen-title")
            yield FzfSelector(items=[], id="pattern-selector", empty_message="No patterns learned")
            yield Footer()

    def on_mount(self) -> None:
        """Fetch and display patterns when screen mounts."""
        self._load_patterns()

    def _load_patterns(self) -> None:
        """Fetch patterns from daemon and populate list."""
        result = self.rpc("get_patterns")
        patterns = result.get("patterns", {}) if result else {}

        # Get theme colors from app (hex strings)
        theme_vars = self.app.get_css_variables()

        items: list[FzfItem] = []
        self.pattern_data = []

        for process in sorted(patterns.keys()):
            states = patterns[process]

            # Handle pairs first
            if "pairs" in states and isinstance(states["pairs"], list):
                for pair_dict in states["pairs"]:
                    if isinstance(pair_dict, dict):
                        ready = pair_dict.get("ready", "")
                        busy = pair_dict.get("busy", "")
                        if ready and busy:
                            item = _build_pair_item(process, ready, busy, len(self.pattern_data), theme_vars)
                            items.append(item)
                            self.pattern_data.append((process, "pair", (ready, busy)))

            # Handle standalone patterns
            for state in ["ready", "busy"]:
                if state not in states:
                    continue

                pattern_list = states[state]
                if not isinstance(pattern_list, list):
                    continue

                for pattern_item in pattern_list:
                    if isinstance(pattern_item, dict):
                        pattern = pattern_item.get("match", "")
                    else:
                        pattern = str(pattern_item)

                    if pattern:
                        item = _build_pattern_item(process, state, pattern, len(self.pattern_data), theme_vars)
                        items.append(item)
                        self.pattern_data.append((process, "standalone", (state, pattern)))

        selector = self.query_one("#pattern-selector", FzfSelector)
        selector.update_items(items)

    def action_edit_pattern(self) -> None:
        """Open editor for selected pattern's process."""
        selector = self.query_one("#pattern-selector", FzfSelector)
        value = selector.get_highlighted_value()
        if value is None:
            return

        try:
            idx = int(value)
            if idx >= len(self.pattern_data):
                return

            process, _, _ = self.pattern_data[idx]

            # Fetch full process config
            result = self.rpc("get_patterns")
            patterns = result.get("patterns", {}) if result else {}
            config = patterns.get(process, {})

            from .pattern_editor_screen import PatternEditorScreen

            self.app.push_screen(PatternEditorScreen(process=process, initial_config=config))
        except (ValueError, IndexError):
            pass

    def action_delete_pattern(self) -> None:
        """Delete the selected pattern or pair."""
        selector = self.query_one("#pattern-selector", FzfSelector)
        value = selector.get_highlighted_value()
        if value is None:
            return

        try:
            idx = int(value)
            if idx >= len(self.pattern_data):
                return

            process, item_type, data = self.pattern_data[idx]

            if item_type == "pair":
                ready, busy = data
                self.rpc("remove_pair", {"process": process, "ready": ready, "busy": busy})
            else:  # standalone
                state, pattern = data
                self.rpc("remove_pattern", {"process": process, "pattern": pattern, "state": state})

            self._load_patterns()
        except (ValueError, IndexError):
            pass

    def on_fzf_selector_selected(self, message: FzfSelector.Selected) -> None:
        """Handle pattern selection - open editor."""
        message.stop()
        self.action_edit_pattern()

    def on_fzf_selector_cancelled(self, message: FzfSelector.Cancelled) -> None:
        """Handle cancel - same as back action."""
        message.stop()
        self.action_back()
