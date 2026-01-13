"""Queue screen - home screen showing pending actions.

PUBLIC API:
  - QueueScreen: DataTable of pending actions with navigation
"""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.widgets import DataTable, Footer, Static

from ._base import TermtapScreen

__all__ = ["QueueScreen"]


class QueueScreen(TermtapScreen):
    """Home screen showing pending actions queue.

    Shows DataTable of pending actions or "Waiting for actions..." when empty.
    Native ↑↓ navigation via DataTable, Enter opens ActionScreen.
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("p", "patterns", "Patterns"),
        Binding("escape", "noop", show=False),  # Override base - root screen has no back
    ]

    def __init__(self):
        super().__init__()
        self.actions: list[dict] = []

    def compose(self) -> ComposeResult:
        yield Static("[bold]Action Queue[/bold]", id="screen-title")
        yield DataTable(id="queue-table")
        yield Static("Waiting for actions...", id="empty-message")
        yield Footer()

    def on_mount(self) -> None:
        """Setup table columns."""
        table = self.query_one("#queue-table", DataTable)
        table.add_columns("ID", "Pane", "State", "Command")
        table.cursor_type = "row"
        self._refresh_display()

    def set_actions(self, actions: list[dict]) -> None:
        """Update actions list and refresh display."""
        self.actions = actions
        self._refresh_display()

    def _refresh_display(self) -> None:
        """Refresh table and empty message visibility."""
        table = self.query_one("#queue-table", DataTable)
        empty = self.query_one("#empty-message", Static)

        table.clear()

        if self.actions:
            table.display = True
            empty.add_class("-hidden")

            for action in self.actions:
                cmd = action.get("command", "")
                if len(cmd) > 40:
                    cmd = cmd[:37] + "..."
                table.add_row(
                    action.get("id", "")[:8],
                    action.get("pane_id", "") or "(select)",
                    action.get("state", ""),
                    cmd,
                    key=action.get("id"),
                )
        else:
            table.display = False
            empty.remove_class("-hidden")

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection - open appropriate action screen."""
        if event.row_key:
            action_id = str(event.row_key.value)
            for action in self.actions:
                if action.get("id") == action_id:
                    self._open_action_screen(action)
                    break

    def _open_action_screen(self, action: dict) -> None:
        """Open appropriate screen for action state."""
        state = action.get("state", "")
        if state == "selecting_pane":
            from .pane_select_screen import PaneSelectScreen

            self.app.push_screen(PaneSelectScreen(action, multi_select=action.get("multi_select", False)))
        else:
            from .pattern_screen import PatternScreen

            self.app.push_screen(PatternScreen(action))

    def action_noop(self) -> None:
        """Do nothing - used to suppress inherited bindings."""
        pass

    def action_quit(self) -> None:
        """Quit application."""
        self.app.exit()

    def action_patterns(self) -> None:
        """Open pattern management screen."""
        from .pattern_list_screen import PatternListScreen

        self.app.push_screen(PatternListScreen())
