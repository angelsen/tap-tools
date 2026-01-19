"""Pattern editor screen with inline YAML editing.

PUBLIC API:
  - PatternEditorScreen: Mini YAML editor for pattern config
"""

import yaml
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Static, TextArea

from ._base import TermtapScreen
from ..widgets.cards import syntax_card, example_card

__all__ = ["PatternEditorScreen"]

HOOK_EXAMPLE = """python:
  hooks:
    '[...]$':
      action: send_keys
      keys: [Enter, Enter]
      debounce: 2s"""

PAIR_EXAMPLE = """npm:
  ready: ['^>']
  busy: ['Installing']"""


class PatternEditorScreen(TermtapScreen):
    """Mini YAML editor for pattern configuration."""

    BINDINGS = [
        ("ctrl+s", "save", "Save"),
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(self, process: str, initial_config: dict):
        super().__init__()
        self.process = process
        self.initial_config = initial_config
        self._valid = True

    def compose(self) -> ComposeResult:
        # Content layer - all screen content
        with Vertical(classes="content-panel"):
            yield Static(f"[bold]Edit: {self.process}[/bold]", id="editor-title")
            yield TextArea("", id="yaml-editor")
            yield Static("[green]Valid YAML[/green]", id="validation")
            yield Horizontal(
                example_card("Hook Example", HOOK_EXAMPLE, "card-warning"),
                example_card("State Example", PAIR_EXAMPLE, "card-success"),
                id="examples-row",
            )
            yield syntax_card()
            yield Footer()

    def on_mount(self) -> None:
        editor = self.query_one("#yaml-editor", TextArea)
        yaml_text = yaml.safe_dump(self.initial_config, default_flow_style=False, sort_keys=False)
        editor.text = yaml_text

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        self._validate()

    def _validate(self) -> None:
        editor = self.query_one("#yaml-editor", TextArea)
        status = self.query_one("#validation", Static)
        try:
            yaml.safe_load(editor.text)
            self._valid = True
            status.update("[green]Valid YAML[/green]")
        except yaml.YAMLError as e:
            self._valid = False
            status.update(f"[red]Invalid: {str(e)[:50]}[/red]")

    def action_save(self) -> None:
        if not self._valid:
            self.notify("Cannot save: Invalid YAML", severity="error")
            return

        editor = self.query_one("#yaml-editor", TextArea)
        config = yaml.safe_load(editor.text)
        self.rpc("update_process_config", {"process": self.process, "config": config})
        self.notify("Saved")
        self.app.pop_screen()

    def action_cancel(self) -> None:
        self.app.pop_screen()
