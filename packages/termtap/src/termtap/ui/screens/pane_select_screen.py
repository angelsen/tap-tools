"""Pane selection screen.

PUBLIC API:
  - PaneSelectScreen: Select a pane from available panes
"""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.widgets import Footer, OptionList, Static

from rich.text import Text

from ._base import TermtapScreen
from ..widgets import FzfSelector, FzfItem, PreviewPane
from ...tmux import capture_last_n

__all__ = ["PaneSelectScreen"]


class PaneSelectScreen(TermtapScreen):
    """Select pane(s) from list.

    Args:
        action: Action dict with id, pane_id, etc.
        multi_select: If True, allow multiple selection
    """

    # Static bindings - FzfSelector handles actual key behavior
    # Tab/Enter shown for multi, Enter for single (footer shows all, FzfSelector filters)
    BINDINGS = [
        Binding("tab", "noop", "Toggle", show=True),
        Binding("enter", "noop", "Select", show=True),
        Binding("escape", "back", "Cancel"),
        Binding("ctrl+underscore", "toggle_preview", "Preview", priority=True),
    ]

    def __init__(self, action: dict, multi_select: bool = False):
        super().__init__()
        self.action = action
        self.multi_select = multi_select

    def compose(self) -> ComposeResult:
        yield Static("[bold]Select Pane[/bold]", id="screen-title")

        # Determine orientation based on terminal width
        orientation = "-horizontal" if self.app.size.width >= 120 else "-vertical"
        with Container(classes=f"pane-selector {orientation}"):
            yield PreviewPane(id="preview")  # Always in DOM
            yield FzfSelector([], multi_select=self.multi_select)
        yield Footer()

    def on_mount(self) -> None:
        """Load pane list from daemon."""
        result = self.rpc("ls")
        if result:
            panes = result.get("panes", [])

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

                # Display: Rich Text with colors
                label = Text()
                label.append(session.ljust(max_session), style="cyan")
                label.append("  ")
                label.append(pane_idx.ljust(max_pane_idx), style="dim")
                label.append("  ")
                label.append(process, style="green")

                # Search: concatenate searchable fields
                search_text = f"{session} {pane_idx} {process}"

                items.append(FzfItem(display=label, value=pane_id, search=search_text))

            # Update selector with live pane list
            selector = self.query_one(FzfSelector)
            selector.update_items(items)

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

    def action_noop(self) -> None:
        """Placeholder - FzfSelector handles Enter key internally."""
        pass

    def action_toggle_preview(self) -> None:
        """Toggle preview visibility via CSS class."""
        preview = self.query_one("#preview")
        preview.toggle_class("-visible")
        if preview.has_class("-visible"):
            self._update_preview()

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        """Update preview when navigation changes."""
        preview = self.query_one("#preview")
        if preview.has_class("-visible"):
            self._update_preview()

    def _update_preview(self) -> None:
        """Fetch and update preview content for highlighted pane."""
        preview = self.query_one("#preview", PreviewPane)

        selector = self.query_one(FzfSelector)
        pane_id = selector.get_highlighted_value()

        if pane_id:
            content = capture_last_n(pane_id, 30)
            preview.set_content(content)
        else:
            preview.set_content("(preview unavailable)")

    def _resolve_action(self, result: dict) -> None:
        """Send resolve RPC and pop screen."""
        action_id = self.action.get("id")
        if action_id:
            self.rpc("resolve", {"action_id": action_id, "result": result})
        self.app.pop_screen()
