"""Preview pane widget for displaying pane content.

PUBLIC API:
  - PreviewPane: Scrollable preview of pane content
"""

from .base import BaseTerminalPane

__all__ = ["PreviewPane"]


class PreviewPane(BaseTerminalPane):
    """Scrollable preview of pane content.

    Read-only TextArea with no wrapping for raw terminal output.
    All styling via companion.tcss - no DEFAULT_CSS to avoid conflicts.
    """

    can_focus = False  # Display-only, no cursor/selection
