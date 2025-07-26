"""Handler for Claude TUI."""

import re
from typing import Optional

from . import ProcessHandler
from ..tree import ProcessNode
from ...tmux import capture_last_n


class ClaudeHandler(ProcessHandler):
    """Handler for Claude interactive TUI."""

    # Patterns for Claude state detection
    _BUSY_PATTERN = re.compile(r"\* (Booping|Jiving)… \(.*esc to interrupt\)")
    _PROMPT_PATTERN = re.compile(r"│\s*>\s*")

    def can_handle(self, process: ProcessNode) -> bool:
        """Handle claude process."""
        return process.name == "claude"

    def is_ready(self, session_id: str) -> tuple[bool, str]:
        """Check if Claude is ready using pane content."""
        # Get last 10 lines of pane
        pane_content = capture_last_n(session_id, 10)

        # Check for busy indicator
        if self._BUSY_PATTERN.search(pane_content):
            return False, "claude generating"

        # Check for prompt
        if self._PROMPT_PATTERN.search(pane_content):
            return True, "claude ready"

        # No clear state
        return False, "claude state unknown"

    def pre_send(self, session_id: str, command: str) -> Optional[str]:
        """Pre-send hook for Claude."""
        # Could add special handling for slash commands
        if command.strip() == "/exit":
            # Could show warning or log
            pass
        return command

    def during_command(self, session_id: str, elapsed: float) -> bool:
        """Claude during_command - no intervention."""
        return True
