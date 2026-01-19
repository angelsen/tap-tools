"""Pane selection screen.

PUBLIC API:
  - PaneSelectScreen: Select a pane from available panes
"""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.widgets import Footer, OptionList, Static

from rich.text import Text

from ._base import TermtapScreen
from ..widgets import FzfSelector, FzfItem, PreviewPane
from ...pane import Pane

__all__ = ["PaneSelectScreen"]


class PaneSelectScreen(TermtapScreen):
    """Select pane(s) from list.

    Args:
        action: Action dict with id, pane_id, etc.
        multi_select: If True, allow multiple selection

    Key bindings:
    - Type to filter, arrows to navigate (FzfSelector)
    - Enter/Tab: Select (FzfSelector handles)
    - Escape: Cancel
    - Ctrl+S: Toggle sort order
    - Ctrl+-: Toggle preview
    """

    BINDINGS = [
        ("escape", "back", "Cancel"),
        ("ctrl+s", "toggle_sort", "Sort"),
        Binding("ctrl+underscore", "toggle_preview", "Preview", key_display="^-"),
    ]

    def __init__(self, action: dict, multi_select: bool = False):
        super().__init__()
        self.action = action
        self.multi_select = multi_select
        self._show_working_set = True  # Default: working set only
        self._all_panes = []  # Store all panes for filtering

    def compose(self) -> ComposeResult:
        # Content layer - all screen content
        with Vertical(classes="content-panel"):
            yield Static("[bold]Select Pane[/bold]", classes="screen-title")

            # Determine orientation based on terminal width
            orientation = "-horizontal" if self.app.size.width >= 120 else "-vertical"
            with Container(classes=f"pane-selector {orientation}"):
                yield PreviewPane(id="preview")  # Always in DOM
                yield FzfSelector([], multi_select=self.multi_select)
            yield Footer()

    def on_mount(self) -> None:
        """Load pane list from daemon."""
        # Show preview by default using Python display property
        preview = self.query_one("#preview")
        preview.display = True

        result = self.rpc("ls")
        if result:
            self._all_panes = result.get("panes", [])
            self._update_pane_list()

    def _update_pane_list(self) -> None:
        """Filter and sort panes based on mode."""
        panes = self._all_panes

        if self._show_working_set:
            # Only panes with last_accessed > 0, sorted by recency
            filtered = [p for p in panes if p.get("last_accessed", 0) > 0]
            filtered.sort(key=lambda p: p.get("last_accessed", 0), reverse=True)
            # Fall back to all panes if working set is empty
            if not filtered:
                filtered = panes
            panes = filtered

        # Calculate max widths for alignment
        max_session = max((len(p.get("session", "")) for p in panes), default=0)
        max_pane_idx = max((len(f"{p['window_index']}.{p['pane_index']}") for p in panes), default=0)

        # Build FzfItems
        items = []
        for p in panes:
            session = p.get("session", "")
            pane_idx = f"{p['window_index']}.{p['pane_index']}"
            process = p.get("pane_current_command", "")
            pane_id = p.get("pane_id", "")

            # Display: Rich Text with theme-aware markup
            label = Text()
            label.append(session.ljust(max_session), style="bold")
            label.append("  ")
            label.append(pane_idx.ljust(max_pane_idx), style="dim")
            label.append("  ")
            label.append(process, style="italic")

            # Search: concatenate searchable fields
            search_text = f"{session} {pane_idx} {process}"

            items.append(FzfItem(display=label, value=pane_id, search=search_text))

        # Update selector with live pane list
        selector = self.query_one(FzfSelector)
        selector.update_items(items)

    def action_toggle_sort(self) -> None:
        """Toggle between working set and all panes."""
        self._show_working_set = not self._show_working_set
        self._update_pane_list()

    def on_fzf_selector_selected(self, event: FzfSelector.Selected) -> None:
        """Handle pane selection from FzfSelector."""
        if self.multi_select:
            panes = event.value if isinstance(event.value, list) else [event.value]
            self._resolve_action({"panes": panes})
        else:
            pane = event.value if isinstance(event.value, str) else event.value[0]
            self._resolve_action({"pane": pane})

    def on_fzf_selector_cancelled(self, event: FzfSelector.Cancelled) -> None:
        """Handle cancellation from FzfSelector."""
        self.app.pop_screen()

    def on_resize(self, event) -> None:
        """Update preview when size is known/changed."""
        preview = self.query_one("#preview", PreviewPane)
        if preview.display:
            self._update_preview()

    def action_toggle_preview(self) -> None:
        """Toggle preview visibility using Python display property."""
        preview = self.query_one("#preview")
        preview.display = not preview.display
        if preview.display:
            # Defer until layout updates
            self.call_after_refresh(self._update_preview)

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        """Update preview when navigation changes."""
        preview = self.query_one("#preview")
        if preview.display:
            self._update_preview()

    def _update_preview(self) -> None:
        """Fetch content based on widget size."""
        preview = self.query_one("#preview", PreviewPane)

        lines = preview.get_line_capacity()
        if lines is None:
            # Size not known yet - will be called again from on_resize
            return

        selector = self.query_one(FzfSelector)
        pane_id = selector.get_highlighted_value()

        if pane_id:
            pane = Pane.capture_tail(pane_id, lines)
            preview.set_content(pane.content)
        else:
            preview.set_content("(no pane selected)")

    def _resolve_action(self, result: dict) -> None:
        """Send resolve RPC and pop screen."""
        action_id = self.action.get("id")
        if action_id:
            self.rpc("resolve", {"action_id": action_id, "result": result})
        self.app.pop_screen()
