"""Line buffer with cursor tracking for terminal overwrites.

PUBLIC API:
  - LineBuffer: Single line with cursor position for overwrites
"""


class LineBuffer:
    """Single line with cursor position for overwrites.

    Used by SlimScreen to handle spinners and in-place updates.
    Characters can be overwritten at cursor position (spinners)
    or extended when cursor is beyond current length.
    """

    def __init__(self) -> None:
        self._chars: list[str] = []
        self.cursor: int = 0

    def write(self, text: str) -> None:
        """Write text at cursor, extending if needed.

        For each character:
        - If cursor < len, overwrite existing char (spinner behavior)
        - If cursor >= len, append new char (normal writing)
        - Cursor advances after each char
        """
        for char in text:
            if self.cursor < len(self._chars):
                self._chars[self.cursor] = char
            else:
                self._chars.append(char)
            self.cursor += 1

    def set_cursor(self, col: int) -> None:
        """Set cursor position (0-indexed).

        Used by cursor_to_column() for spinner positioning.
        Negative values clamped to 0.
        """
        self.cursor = max(0, col)

    @property
    def text(self) -> str:
        """Return line as string."""
        return "".join(self._chars)

    def __repr__(self) -> str:
        return f"LineBuffer({self.text!r})"


__all__ = ["LineBuffer"]
