"""FZF-style selector widget with unified keyboard input.

PUBLIC API:
  - FzfItem: NamedTuple(display, value, search) for selector items
  - FzfSelector: Widget that captures all keyboard input for filtering
  - FzfSelector.update_items: Update items in place
  - FzfSelector.get_highlighted_value: Get currently highlighted value
"""

from typing import NamedTuple

from rich.console import RenderableType
from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.fuzzy import FuzzySearch
from textual.message import Message
from textual.widgets import Label, OptionList
from textual.widgets.option_list import Option

__all__ = ["FzfSelector", "FzfItem"]


class FzfItem(NamedTuple):
    """Item for FzfSelector.

    Attributes:
        display: Rich renderable (Panel, Text, str, etc.)
        value: String returned on selection
        search: Text used for fuzzy matching
    """

    display: RenderableType
    value: str
    search: str


class FzfSelector(Vertical):
    """FZF-style selector - type to filter, arrows to navigate.

    Unlike traditional widgets, this captures ALL keyboard input at the widget
    level. No need to focus an input field - just start typing and it filters.

    Key bindings (single mode):
    - Type: Filter list
    - Backspace: Remove last filter char
    - Up/Down: Navigate highlighted item
    - Enter/Space: Select highlighted item
    - Escape: Cancel selection

    Key bindings (multi mode):
    - Type: Filter list
    - Backspace: Remove last filter char
    - Up/Down: Navigate highlighted item
    - Space/Tab: Toggle selection (●/○)
    - Enter: Confirm all selected items
    - Escape: Cancel selection
    """

    BINDINGS = [
        ("enter", "confirm", "Select"),
        ("escape", "cancel", "Cancel"),
    ]

    class Selected(Message):
        """Posted when an item is selected."""

        def __init__(self, value: str | list[str]) -> None:
            self.value = value
            super().__init__()

    class Cancelled(Message):
        """Posted when selection is cancelled."""

        pass

    def __init__(
        self,
        items: list[FzfItem],
        *,
        multi_select: bool = False,
        empty_message: str | None = None,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize FZF selector.

        Args:
            items: List of FzfItem(display, value, search) items.
            multi_select: Enable multi-select mode with ●/○ markers
            empty_message: Message to show when items list is empty
            name: Widget name
            id: Widget ID
            classes: CSS classes
        """
        super().__init__(name=name, id=id, classes=classes)
        self._all_items = items
        self._filtered = items.copy()
        self._query = ""
        self._multi_select = multi_select
        self._empty_message = empty_message
        self._selected: set[str] = set()
        self._fuzzy = FuzzySearch(case_sensitive=False)

    def compose(self) -> ComposeResult:
        """Compose child widgets."""
        yield Label("", id="query-display")
        yield OptionList(*[Option(self._format_label(item), id=item.value) for item in self._all_items])
        yield Label(self._empty_message or "", id="empty-message")

    def on_mount(self) -> None:
        """Focus widget on mount to capture keys."""
        self.focus()
        self._update_empty_state()

    def on_key(self, event) -> None:
        """Handle all keyboard input.

        FzfSelector captures all keys for filtering. Enter/escape call action
        methods (BINDINGS exist for footer display only).
        """
        key = event.key

        if key == "escape":
            event.stop()
            self.action_cancel()
            return

        if key == "enter":
            event.stop()
            self.action_confirm()
            return

        if key == "space":
            event.stop()
            if self._multi_select:
                self._toggle_current()
            else:
                self._select_current()
            return

        if key == "tab" and self._multi_select:
            event.stop()
            self._toggle_current()
            return

        if key == "up" or key == "down":
            return

        if key == "backspace":
            event.stop()
            if self._query:
                self._query = self._query[:-1]
                self._update_filter()
            return

        if event.is_printable and event.character:
            event.stop()
            self._query += event.character
            self._update_filter()

    def action_confirm(self) -> None:
        """Confirm selection (enter key)."""
        if self._multi_select:
            # If nothing marked, select highlighted item
            if not self._selected:
                option_list = self.query_one(OptionList)
                if option_list.highlighted is not None:
                    option = option_list.get_option_at_index(option_list.highlighted)
                    if option and option.id:
                        self.post_message(self.Selected([str(option.id)]))
                        return
            # Confirm all selected items
            self.post_message(self.Selected(list(self._selected)))
        else:
            self._select_current()

    def action_cancel(self) -> None:
        """Cancel selection (escape key)."""
        self.post_message(self.Cancelled())

    def _format_label(self, item: FzfItem) -> RenderableType:
        """Add selection marker in multi mode."""
        if self._multi_select:
            marker = "● " if item.value in self._selected else "○ "
            if isinstance(item.display, Text):
                result = Text(marker)
                result.append_text(item.display)
                return result
            elif isinstance(item.display, str):
                return f"{marker}{item.display}"
            # For Panel/other: just return display for now
        return item.display

    def _update_filter(self) -> None:
        """Update filter display and filtered list using FuzzySearch."""
        query_label = self.query_one("#query-display", Label)
        query_label.update(f"Query: {self._query}" if self._query else "")

        if not self._query:
            self._filtered = self._all_items.copy()
        else:
            # Use FuzzySearch to score and rank matches
            matches = []
            for item in self._all_items:
                score, _ = self._fuzzy.match(self._query, item.search)
                if score > 0:
                    matches.append((score, item))
            # Sort by score (descending)
            matches.sort(key=lambda x: -x[0])
            self._filtered = [item for _, item in matches]

        # Rebuild options with updated labels (reset highlight for new results)
        self._rebuild_options(reset_highlight=True)

    def _rebuild_options(self, reset_highlight: bool = False) -> None:
        """Rebuild option list with current filtered items and selection state."""
        option_list = self.query_one(OptionList)
        current_highlight = option_list.highlighted
        option_list.clear_options()

        for item in self._filtered:
            formatted = self._format_label(item)
            option_list.add_option(Option(formatted, id=item.value))

        if len(self._filtered) > 0:
            if reset_highlight or current_highlight is None or current_highlight >= len(self._filtered):
                option_list.highlighted = 0
            else:
                option_list.highlighted = current_highlight

    def _toggle_current(self) -> None:
        """Toggle selection of highlighted item."""
        option_list = self.query_one(OptionList)
        if option_list.highlighted is not None:
            option = option_list.get_option_at_index(option_list.highlighted)
            if option and option.id:
                value = str(option.id)
                if value in self._selected:
                    self._selected.discard(value)
                else:
                    self._selected.add(value)
                # Rebuild to update markers
                self._rebuild_options()

    def _select_current(self) -> None:
        """Select currently highlighted item."""
        option_list = self.query_one(OptionList)
        if option_list.highlighted is not None:
            option = option_list.get_option_at_index(option_list.highlighted)
            if option and option.id:
                self.post_message(self.Selected(str(option.id)))

    def _update_empty_state(self) -> None:
        """Show/hide empty message based on items."""
        empty_label = self.query_one("#empty-message", Label)
        option_list = self.query_one(OptionList)

        if self._all_items:
            empty_label.display = False
            option_list.display = True
        else:
            empty_label.display = True
            option_list.display = False

    def update_items(self, items: list[FzfItem]) -> None:
        """Update items and rebuild the option list.

        Args:
            items: New list of FzfItem items.
        """
        self._all_items = items
        self._filtered = items.copy()
        self._query = ""
        self._selected.clear()

        # Clear query display
        self.query_one("#query-display", Label).update("")

        # Rebuild options
        self._rebuild_options(reset_highlight=True)

        # Toggle empty message visibility
        self._update_empty_state()

    def get_highlighted_value(self) -> str | None:
        """Get value of currently highlighted item.

        Returns:
            The value string of the highlighted item, or None if nothing highlighted.
        """
        option_list = self.query_one(OptionList)
        if option_list.highlighted is not None:
            option = option_list.get_option_at_index(option_list.highlighted)
            if option and option.id:
                return str(option.id)
        return None

    @on(OptionList.OptionSelected)
    def _option_selected(self, event: OptionList.OptionSelected) -> None:
        """Swallow mouse clicks - keyboard only."""
        event.stop()
