"""Base widget classes.

PUBLIC API:
  - BaseTerminalPane: Read-only terminal output base
"""

from textual.widgets import TextArea

__all__ = ["BaseTerminalPane"]


class BaseTerminalPane(TextArea):
    """Base for read-only terminal panes."""

    def __init__(self, content: str = "", **kwargs):
        super().__init__(content, read_only=True, show_line_numbers=False, soft_wrap=False, **kwargs)
        self._size_known = False

    def on_resize(self, event) -> None:
        if event.size.height > 0:
            self._size_known = True

    def get_line_capacity(self) -> int | None:
        if not self._size_known:
            return None
        return self.size.height

    def set_content(self, text: str) -> None:
        self.load_text(text or "(empty)")
        self.scroll_end(animate=False, immediate=False)
