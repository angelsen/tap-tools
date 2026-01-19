"""Pattern marking screen.

PUBLIC API:
  - PatternScreen: Mark patterns for state detection
"""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.widgets import Footer, Static

from ._base import TermtapScreen
from ..widgets import DslReference, OutputPane, PatternEditor

__all__ = ["PatternScreen"]


class PatternScreen(TermtapScreen):
    """Mark patterns for state detection.

    Shows OutputPane with pane content and PatternEditor for DSL patterns.
    User can select text to add as literals, or edit DSL directly.
    Bottom shows DSL syntax reference and examples.

    Key bindings:
    - a/u: Add/undo selection (handled by OutputPane when focused)
    - r/b/p: Resolve ready/busy/toggle pair mode (screen-level)
    - ctrl+r: Refresh pane output
    - ?: Show DSL syntax reference
    """

    BINDINGS = [
        ("r", "resolve_ready", "Ready"),
        ("b", "resolve_busy", "Busy"),
        ("p", "resolve_pair", "Pair"),
        ("ctrl+r", "refresh", "Refresh"),
        Binding("question_mark", "show_syntax", "Syntax", key_display="?"),
        ("escape", "back"),
    ]

    def __init__(self, action: dict):
        super().__init__()
        self.action = action
        self.pair_mode_enabled = False
        self._data_loaded = False
        self._current_process = "unknown"

    def compose(self) -> ComposeResult:
        # Content layer - all screen content
        with VerticalScroll(classes="content-panel"):
            yield Static("Process: [bold]...[/bold]", id="process-info")
            yield Static("", id="pane-info")
            yield OutputPane("")
            yield PatternEditor()
            yield DslReference()
        yield Footer()

    def on_mount(self) -> None:
        """Schedule data load after layout is complete."""
        self.call_after_refresh(self._load_live_data)

    def on_resize(self, event) -> None:
        """Retry data load when size becomes known."""
        if not self._data_loaded and event.size.height > 0:
            self._load_live_data()

    def _load_live_data(self) -> None:
        """Fetch live pane data from daemon."""
        if self._data_loaded:
            return

        pane_id = self.action.get("pane_id")
        if not pane_id:
            return

        output_pane = self.query_one(OutputPane)
        lines = output_pane.get_line_capacity()

        if lines is None:
            return

        self._data_loaded = True

        result = self.rpc("get_pane_data", {"pane_id": pane_id, "lines": lines})

        if result:
            # Update display widgets
            self._current_process = result.get("process", "unknown")
            self._update_process_header()
            self.query_one("#pane-info", Static).update(result.get("swp", ""))

            content = result.get("content", "")
            # Set content after refresh to ensure widget is properly mounted
            self.call_after_refresh(lambda: output_pane.set_content(content))

    def _update_process_header(self) -> None:
        """Update process header with optional pair mode indicator."""
        if self.pair_mode_enabled:
            process_text = f"Process: [bold]{self._current_process}[/bold][right]PAIR MODE[/right]"
        else:
            process_text = f"Process: [bold]{self._current_process}[/bold]"

        process_info = self.query_one("#process-info", Static)
        process_info.update(process_text)

        # Toggle CSS class for background color
        if self.pair_mode_enabled:
            process_info.add_class("-pair-mode")
        else:
            process_info.remove_class("-pair-mode")

    def on_output_pane_add_selection(self, event: OutputPane.AddSelection) -> None:
        """Handle add selection message from OutputPane."""
        editor = self.query_one(PatternEditor)
        editor.add_entry(event.text, event.row, event.col)

    def on_output_pane_undo_selection(self, event: OutputPane.UndoSelection) -> None:
        """Handle undo selection message from OutputPane."""
        editor = self.query_one(PatternEditor)
        if not editor.undo_entry():
            self.notify("No entries to undo")

    def action_refresh(self) -> None:
        """Refresh pane output and clear pattern."""
        # Reset data loaded flag and reload
        self._data_loaded = False
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
        """Resolve with ready state (respects pair mode toggle)."""
        self._resolve_with_state("ready", pair_mode=self.pair_mode_enabled)

    def action_resolve_pair(self) -> None:
        """Toggle pair mode on/off."""
        self.pair_mode_enabled = not self.pair_mode_enabled
        self._update_process_header()
        mode_text = "ON" if self.pair_mode_enabled else "OFF"
        self.notify(f"Pair mode: {mode_text}")

    def action_resolve_busy(self) -> None:
        """Resolve with busy state OR set linked busy for pair mode."""
        action_state = self.action.get("state")

        if action_state == "watching" and self.action.get("pair_mode"):
            self._set_linked_busy()
        else:
            self._resolve_with_state("busy")

    def _resolve_with_state(self, state: str, pair_mode: bool = False) -> None:
        """Resolve action with state and learn pattern."""
        editor = self.query_one(PatternEditor)
        pattern = editor.get_pattern()

        # Learn pattern ONLY if NOT in pair mode
        # (In pair mode, pattern will be learned as a pair when busy is marked)
        if pattern and not pair_mode:
            pane_id = self.action.get("pane_id")
            if pane_id:
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
        result: dict = {"state": state, "pair_mode": pair_mode}
        if pattern:
            result["pattern"] = pattern
        self._resolve_action(result)

    def _set_linked_busy(self) -> None:
        """Set linked busy pattern and complete action immediately."""
        editor = self.query_one(PatternEditor)
        pattern = editor.get_pattern()
        if pattern:
            result = self.rpc(
                "set_linked_busy",
                {
                    "action_id": self.action.get("id"),
                    "pattern": pattern,
                },
            )
            if result and result.get("ok"):
                self.notify("Pair learned, action completed")
                self.app.pop_screen()
            else:
                error_msg = result.get("error", "Unknown error") if result else "No response"
                self.notify(f"Error: {error_msg}", severity="error")

    def _resolve_action(self, result: dict) -> None:
        """Send resolve RPC and pop screen."""
        action_id = self.action.get("id")
        if action_id:
            self.rpc("resolve", {"action_id": action_id, "result": result})
        self.app.pop_screen()
