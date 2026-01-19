"""Output pane with cursor-based selection.

PUBLIC API:
  - OutputPane: Read-only pane output with cursor and selection
"""

from __future__ import annotations

from textual.message import Message

from .base import BaseTerminalPane

__all__ = ["OutputPane"]


class OutputPane(BaseTerminalPane):
    """Read-only pane output with cursor and selection."""

    BINDINGS = [
        ("a", "add_selection", "Add"),
        ("u", "undo_selection", "Undo"),
    ]

    class AddSelection(Message):
        """Posted when user wants to add selection to pattern."""

        def __init__(self, text: str, row: int, col: int) -> None:
            self.text = text
            self.row = row
            self.col = col
            super().__init__()

    class UndoSelection(Message):
        """Posted when user wants to undo last pattern entry."""

        pass

    def action_add_selection(self) -> None:
        """Add current selection/cursor position to pattern."""
        text, row, col = self.get_entry_for_pattern()
        if text:
            self.post_message(self.AddSelection(text, row, col))

    def action_undo_selection(self) -> None:
        """Undo last pattern entry."""
        self.post_message(self.UndoSelection())

    def get_entry_for_pattern(self) -> tuple[str, int, int]:
        """Get text and position for pattern entry.

        Returns:
            (text, row, col)

        Behavior:
        - Selection: selected text + selection start position
        - Col 0: full line, col=0
        - Mid-line: start to cursor, col=0
        """
        if self.selected_text:
            start, _ = self.selection
            return self.selected_text, start[0], start[1]

        row, col = self.cursor_location
        line = self.document.get_line(row)

        if col == 0:
            return line, row, 0
        else:
            return line[:col], row, 0
