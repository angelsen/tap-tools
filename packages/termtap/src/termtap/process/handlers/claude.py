"""Claude CLI handler using content detection.

# to_agent: Required per handlers/README.md
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
    """Claude CLI handler using content-based state detection.

    Uses pane content to determine Claude's state since process-based
    detection is unreliable (Claude always has MCP server children).
    """

    _handles = ["claude"]

    def can_handle(self, pane: Pane) -> bool:
        """Check if this handler manages Claude CLI processes."""
        return bool(pane.process and pane.process.name in self._handles)

    def is_ready(self, pane: Pane) -> tuple[bool | None, str]:
        """Determine if Claude is ready for input using content detection.

        Args:
            pane: Pane with process information.
        """
        content = pane.visible_content

        if "esc to interrupt)" in content:
            return False, "thinking"

        if "\xa0>\xa0" in content:
            return True, "ready"

        return None, "no prompt detected"
