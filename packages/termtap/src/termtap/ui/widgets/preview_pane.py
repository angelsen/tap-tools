"""Preview pane widget for displaying pane content.

PUBLIC API:
  - PreviewPane: Scrollable preview of pane content
"""

from textual.widgets import Static

__all__ = ["PreviewPane"]


class PreviewPane(Static):
    """Scrollable preview of pane content.

    All styling via companion.tcss - no DEFAULT_CSS to avoid conflicts.
    """

    def set_content(self, text: str) -> None:
        """Update preview content.

        Args:
            text: Content to display. Empty string shows "(empty)".
        """
        self.update(text or "(empty)")
