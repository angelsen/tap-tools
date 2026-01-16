"""Output pane with cursor-based selection.

PUBLIC API:
  - OutputPane: Read-only pane output with cursor and selection
"""

from __future__ import annotations

from .base import BaseTerminalPane

__all__ = ["OutputPane"]


class OutputPane(BaseTerminalPane):
    """Read-only pane output with cursor and selection."""

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
