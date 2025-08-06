"""Claude handler - handles Claude CLI through content detection.

Internal module - no public API.

TESTING LOG:
Date: 2025-01-30
System: Linux 6.12.39-1-lts
Process: claude (Anthropic Claude CLI)
Tracking: ~/.termtap/tracking/20250730_002715_claude
         ~/.termtap/tracking/20250730_013620_what_is_22

Observed patterns:
- "esc to interrupt)": Claude is thinking/processing (busy)
- "\xa0>\xa0" (with non-breaking spaces): Claude ready for input
- Claude always shows prompt, even when busy

Notes:
- Must check busy pattern first as it takes precedence
- Claude always has children (MCP servers)
- Process-based detection unreliable, requires content detection
"""

from . import ProcessHandler
from ...pane import Pane


class _ClaudeHandler(ProcessHandler):
    """Handler for Claude CLI - content-based detection."""

    handles = ["claude"]

    def can_handle(self, pane: Pane) -> bool:
        """Check if this handler manages this process."""
        return bool(pane.process and pane.process.name in self.handles)

    def is_ready(self, pane: Pane) -> tuple[bool | None, str]:
        """Determine if Claude is ready for input using content detection.

        Based on tracking data observations.
        """
        # Get visible content
        content = pane.visible_content

        # Check busy state first (takes precedence)
        if "esc to interrupt)" in content:
            return False, "thinking"

        # Check for ready prompt (non-breaking space version)
        if "\xa0>\xa0" in content:
            return True, "ready"

        # Cannot determine state from content
        return None, "no prompt detected"
