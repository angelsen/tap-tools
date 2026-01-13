"""Pattern marking screen.

PUBLIC API:
  - PatternScreen: Mark patterns for state detection
"""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Static

from ._base import TermtapScreen
from ..widgets import DslReference, OutputPane, PatternEditor

__all__ = ["PatternScreen"]


class PatternScreen(TermtapScreen):
    """Mark patterns for state detection.

    Shows OutputPane with pane content and PatternEditor for DSL patterns.
    User can select text to add as literals, or edit DSL directly.
    Bottom shows DSL syntax reference and examples.
    """

    BINDINGS = [
        Binding("a", "add_to_pattern", "Add"),
        Binding("u", "undo_entry", "Undo"),
        Binding("ctrl+r", "refresh", "Refresh"),
        Binding("r", "resolve_ready", "Ready"),
        Binding("b", "resolve_busy", "Busy"),
        Binding("question_mark", "show_syntax", "Syntax"),
        Binding("escape", "back", "Back"),
    ]

    def __init__(self, action: dict):
        super().__init__()
        self.action = action

    def compose(self) -> ComposeResult:
        yield Static("Process: [bold]...[/bold]", id="process-info")
        yield Static("", id="pane-info")
        yield OutputPane("")
        yield PatternEditor()
        yield DslReference()
        yield Footer()

    def on_mount(self) -> None:
        """Load live pane data."""
        self._load_live_data()

    def _load_live_data(self) -> None:
        """Fetch live pane data from daemon."""
        pane_id = self.action.get("pane_id")
        if not pane_id:
            return

        result = self.rpc("get_pane_data", {"pane_id": pane_id})
        if result:
            # Update display widgets
            self.query_one("#process-info", Static).update(f"Process: [bold]{result.get('process', 'unknown')}[/bold]")
            self.query_one("#pane-info", Static).update(result.get("swp", ""))
            self.query_one(OutputPane).set_content(result.get("content", ""))

    def action_add_to_pattern(self) -> None:
        """Add entry with position tracking."""
        output_pane = self.query_one(OutputPane)
        editor = self.query_one(PatternEditor)

        text, row, col = output_pane.get_entry_for_pattern()
        if text:
            editor.add_entry(text, row, col)

    def action_undo_entry(self) -> None:
        """Remove last entry and rebuild."""
        editor = self.query_one(PatternEditor)
        editor.undo_entry()

    def action_refresh(self) -> None:
        """Refresh pane output and clear pattern."""
        self._load_live_data()
        editor = self.query_one(PatternEditor)
        editor.clear_pattern()

    def action_back(self) -> None:
        """Go back to queue."""
        self.app.pop_screen()

    def action_show_syntax(self) -> None:
        """Show full DSL syntax reference."""
        from .dsl_syntax_screen import DslSyntaxScreen

        self.app.push_screen(DslSyntaxScreen())

    def action_resolve_ready(self) -> None:
        """Resolve with ready state."""
        self._resolve_with_state("ready")

    def action_resolve_busy(self) -> None:
        """Resolve with busy state."""
        self._resolve_with_state("busy")

    def _resolve_with_state(self, state: str) -> None:
        """Resolve action with state and learn pattern."""
        editor = self.query_one(PatternEditor)
        pattern = editor.get_pattern()

        # Learn pattern FIRST (before resolve triggers WATCHING state)
        pane_id = self.action.get("pane_id")
        if pattern and pane_id:
            pane_data = self.rpc("get_pane_data", {"pane_id": pane_id})
            if pane_data:
                process_name = pane_data.get("process")
                if process_name:
                    self.rpc(
                        "learn_pattern",
                        {
                            "process": process_name,
                            "pattern": pattern,
                            "state": state,
                        },
                    )

        # Then resolve (which transitions to WATCHING state)
        result: dict = {"state": state}
        if pattern:
            result["pattern"] = pattern
        self._resolve_action(result)

    def _resolve_action(self, result: dict) -> None:
        """Send resolve RPC and pop screen."""
        action_id = self.action.get("id")
        if action_id:
            self.rpc("resolve", {"action_id": action_id, "result": result})
        self.app.pop_screen()
