"""Queue screen - home screen showing pending actions.

PUBLIC API:
  - QueueScreen: DataTable of pending actions with navigation
"""

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import DataTable, Footer, Static

from ._base import TermtapScreen
from ..widgets import Background, LogoText

__all__ = ["QueueScreen"]

# Pre-rendered termtap logo (ansi_shadow font, 6 lines x 61 chars)
LOGO_TEXT = r"""████████╗███████╗██████╗ ███╗   ███╗████████╗ █████╗ ██████╗
╚══██╔══╝██╔════╝██╔══██╗████╗ ████║╚══██╔══╝██╔══██╗██╔══██╗
   ██║   █████╗  ██████╔╝██╔████╔██║   ██║   ███████║██████╔╝
   ██║   ██╔══╝  ██╔══██╗██║╚██╔╝██║   ██║   ██╔══██║██╔═══╝
   ██║   ███████╗██║  ██║██║ ╚═╝ ██║   ██║   ██║  ██║██║
   ╚═╝   ╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝   ╚═╝   ╚═╝  ╚═╝╚═╝"""


class QueueScreen(TermtapScreen):
    """Home screen showing pending actions queue.

    Shows DataTable of pending actions or animated logo when empty.
    Native ↑↓ navigation via DataTable, Enter opens ActionScreen.
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("p", "patterns", "Patterns"),
        ("delete", "cancel_action", "Cancel"),
        ("escape", "noop"),  # Override base - root screen has no back
    ]

    def __init__(self):
        super().__init__()
        self.actions: list[dict] = []

    def compose(self) -> ComposeResult:
        with Background(dim=False):
            with Vertical(classes="content-card"):
                yield LogoText(
                    LOGO_TEXT,
                    colors=["$primary", "$accent"],
                    animate=True,
                    fps=8,
                )

                yield Static("[bold]Action Queue[/bold]", classes="screen-title")
                yield DataTable(id="queue-table")

        yield Footer()

    def on_mount(self) -> None:
        """Setup table columns."""
        table = self.query_one("#queue-table", DataTable)
        table.add_columns("ID", "Pane", "State", "Command")
        table.cursor_type = "row"
        self._refresh_display()

    def on_screen_suspend(self) -> None:
        """Pause animation when switching to other screens."""
        logo = self.query_one(LogoText)
        logo.animated = False

    def on_screen_resume(self) -> None:
        """Resume animation when returning to queue screen."""
        logo = self.query_one(LogoText)
        logo.animated = True

    def set_actions(self, actions: list[dict]) -> None:
        """Update actions list and refresh display."""
        self.actions = actions
        self._refresh_display()

    def _refresh_display(self) -> None:
        """Refresh table visibility and content."""
        table = self.query_one("#queue-table", DataTable)
        title = self.query_one(".screen-title", Static)

        table.clear()

        has_actions = bool(self.actions)

        title.display = has_actions
        table.display = has_actions

        if has_actions:
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

    def action_cancel_action(self) -> None:
        """Cancel the selected action from queue."""
        table = self.query_one("#queue-table", DataTable)
        if table.cursor_row is None or not self.actions:
            return
        if table.cursor_row >= len(self.actions):
            return
        action_id = self.actions[table.cursor_row].get("id")
        if action_id:
            self.rpc("cancel", {"action_id": action_id})
