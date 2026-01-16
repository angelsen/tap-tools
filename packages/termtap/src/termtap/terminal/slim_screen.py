"""pyte-compatible terminal screen with ring buffer semantics.

PUBLIC API:
  - SlimScreen: Minimal terminal screen with ring buffer
"""

import logging

from .line_buffer import LineBuffer

logger = logging.getLogger(__name__)


class SlimScreen:
    """Minimal terminal screen with ring buffer semantics.

    Key design decisions (from research):
    1. Single buffer with preserve_before boundary (no dual buffers)
    2. Logical line indices (base_idx tracks offset)
    3. cursor_position() offsets by preserve_before
    4. Lines extend only on draw(), not cursor movement
    5. debug() must be a METHOD (pyte calls it for unknown sequences)

    Ring buffer model:
    - base_idx: logical index of lines[0] (increments as old lines drop)
    - preserve_before: logical index (never adjusted)
    - Access: lines[logical_idx - base_idx]
    """

    def __init__(self, max_lines: int = 5000) -> None:
        self.lines: list[LineBuffer] = []
        self.max_lines: int = max_lines

        # Ring buffer: logical index of lines[0]
        self.base_idx: int = 0

        # Alternate screen boundary (logical index)
        self.preserve_before: int = 0

        # Cursor state
        self.cursor_row: int = 0
        self.cursor_col: int = 0

        # Debug logging (optional)
        self._debug_mode: bool = False
        self.debug_log: list[str] = []

    # --- Ring buffer helpers ---

    def _logical_to_physical(self, logical: int) -> int | None:
        """Convert logical index to physical. None if out of range."""
        physical = logical - self.base_idx
        if 0 <= physical < len(self.lines):
            return physical
        return None

    def _current_logical(self) -> int:
        """Current logical line count."""
        return self.base_idx + len(self.lines)

    def _trim_if_needed(self) -> None:
        """Enforce max_lines, increment base_idx."""
        while len(self.lines) > self.max_lines:
            self.lines.pop(0)
            self.base_idx += 1

    def _ensure_row(self, row: int) -> None:
        """Ensure row exists (physical index, offset-adjusted)."""
        actual_row = self.preserve_before + row
        physical = self._logical_to_physical(actual_row)

        if physical is None:
            # Need to extend
            while self._current_logical() <= actual_row:
                self.lines.append(LineBuffer())
            self._trim_if_needed()

    # --- pyte screen interface (required methods) ---

    def draw(self, data: str) -> None:
        """Draw text at cursor position."""
        self._ensure_row(self.cursor_row)
        physical = self._logical_to_physical(self.preserve_before + self.cursor_row)
        if physical is not None:
            self.lines[physical].write(data)
            self.cursor_col += len(data)

    def linefeed(self) -> None:
        """Move cursor down one line."""
        self.cursor_row += 1
        self.cursor_col = 0

    def carriage_return(self) -> None:
        """Return cursor to column 0."""
        self.cursor_col = 0
        physical = self._logical_to_physical(self.preserve_before + self.cursor_row)
        if physical is not None:
            self.lines[physical].set_cursor(0)

    def cursor_position(self, row: int = 1, col: int = 1) -> None:
        """Move cursor to position (1-indexed from terminal).

        NOTE: Does NOT extend lines. Only draw() creates lines.
        """
        self.cursor_row = row - 1  # Convert to 0-indexed
        self.cursor_col = col - 1

    def cursor_to_column(self, col: int = 1) -> None:
        """Move cursor to column (1-indexed). Used by spinners."""
        self.cursor_col = col - 1
        physical = self._logical_to_physical(self.preserve_before + self.cursor_row)
        if physical is not None:
            self.lines[physical].set_cursor(self.cursor_col)

    def cursor_to_line(self, row: int = 1) -> None:
        """Move cursor to line (1-indexed)."""
        self.cursor_row = row - 1

    def cursor_up(self, count: int = 1) -> None:
        """Move cursor up."""
        self.cursor_row = max(0, self.cursor_row - count)

    def cursor_down(self, count: int = 1) -> None:
        """Move cursor down."""
        self.cursor_row += count

    def cursor_down1(self, count: int = 1) -> None:
        """CNL - Cursor Next Line."""
        self.cursor_down(count)
        self.cursor_col = 0

    def cursor_up1(self, count: int = 1) -> None:
        """CPL - Cursor Previous Line."""
        self.cursor_up(count)
        self.cursor_col = 0

    def cursor_forward(self, count: int = 1) -> None:
        """Move cursor forward."""
        self.cursor_col += count

    def cursor_back(self, count: int = 1) -> None:
        """Move cursor back."""
        self.cursor_col = max(0, self.cursor_col - count)

    def erase_in_display(self, how: int = 0) -> None:
        """Clear screen (respects preserve_before boundary).

        how=0: Cursor to end of display
        how=1: Beginning of display to cursor
        how=2: Clear entire screen → clear from preserve_before onward
        """
        current_logical = self.preserve_before + self.cursor_row
        physical = self._logical_to_physical(current_logical)

        if how == 0:
            # Erase from cursor to end of display
            if physical is not None:
                # Clear from cursor to end of current line
                line = self.lines[physical]
                line._chars = line._chars[: self.cursor_col]

                # Clear all lines after current
                end_physical = len(self.lines)
                for i in range(physical + 1, end_physical):
                    self.lines[i] = LineBuffer()

        elif how == 1:
            # Erase from beginning of display to cursor
            start_physical = self._logical_to_physical(self.preserve_before)
            if start_physical is not None and physical is not None:
                # Clear all lines before current
                for i in range(start_physical, physical):
                    self.lines[i] = LineBuffer()

                # Clear from start of current line to cursor
                line = self.lines[physical]
                line._chars = [" "] * self.cursor_col + line._chars[self.cursor_col :]

        elif how == 2:
            # Clear entire screen (all scrollback - we don't track pane dimensions)
            physical_start = self._logical_to_physical(self.preserve_before)
            if physical_start is not None:
                self.lines = self.lines[:physical_start]
            self.cursor_row = 0
            self.cursor_col = 0

    def erase_in_line(self, how: int = 0) -> None:
        """Clear part of current line.

        how=0: Cursor to end
        how=1: Start to cursor
        how=2: Entire line
        """
        physical = self._logical_to_physical(self.preserve_before + self.cursor_row)
        if physical is None:
            return
        line = self.lines[physical]
        if how == 0:  # Cursor to end
            line._chars = line._chars[: self.cursor_col]
        elif how == 1:  # Start to cursor
            line._chars = [" "] * self.cursor_col + line._chars[self.cursor_col :]
        elif how == 2:  # Entire line
            line._chars = []
            line.cursor = 0

    def set_mode(self, *modes, private: bool = False) -> None:
        """Handle mode setting. Key: 1049 = alternate screen."""
        if private and 1049 in modes:
            # Enter alternate screen: protect everything before
            self.preserve_before = self._current_logical()
            self.cursor_row = 0
            self.cursor_col = 0

    def reset_mode(self, *modes, private: bool = False) -> None:
        """Handle mode reset. 1049 exit = just keep appending."""
        if private and 1049 in modes:
            # Exit alternate: preserve_before stays, cursor at end
            self.cursor_row = self._current_logical() - self.preserve_before
            self.cursor_col = 0

    def index(self) -> None:
        """IND - Move cursor down, scrolling if at bottom."""
        self.cursor_row += 1

    def reverse_index(self) -> None:
        """RI - Move cursor up, scrolling if at top."""
        self.cursor_row = max(0, self.cursor_row - 1)

    def tab(self) -> None:
        """TAB - Move to next tab stop (every 8 columns)."""
        self.cursor_col = (self.cursor_col + 8) // 8 * 8

    def backspace(self) -> None:
        """BS - Move cursor back one column."""
        self.cursor_col = max(0, self.cursor_col - 1)

    def debug(self, *args, **kwargs) -> None:
        """Handle unknown escape sequences. MUST be a method, not bool."""
        if self._debug_mode:
            self.debug_log.append(f"DEBUG: {args} {kwargs}")

    def __getattr__(self, name: str):
        """Catch-all for unimplemented pyte methods."""

        def noop(*args, **kwargs):
            if self._debug_mode:
                self.debug_log.append(f"UNHANDLED: {name}({args}, {kwargs})")

        return noop

    # --- Our API ---

    def clear(self) -> None:
        """Clear buffer for fresh output capture."""
        self.lines = []
        self.base_idx = 0
        self.cursor_row = 0
        self.cursor_col = 0

    def all_content(self) -> str:
        """Return all buffer content."""
        return "\n".join(line.text for line in self.lines)

    def last_n_lines(self, n: int) -> str:
        """Last N lines for pattern matching."""
        return "\n".join(line.text for line in self.lines[-n:])

    @property
    def text(self) -> str:
        """Full buffer as string."""
        return "\n".join(line.text for line in self.lines)

    @property
    def line_count(self) -> int:
        """Total number of lines in buffer (logical count)."""
        return self._current_logical()


__all__ = ["SlimScreen"]
