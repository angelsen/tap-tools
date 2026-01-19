"""Per-pane terminal state with pattern matching.

PUBLIC API:
  - PaneTerminal: Terminal state for a single pane
"""

import logging
from dataclasses import dataclass
from typing import cast

import pyte

from ..daemon.queue import Action
from ..handler.patterns import PatternStore
from .slim_screen import SlimScreen

__all__ = ["PaneTerminal"]

logger = logging.getLogger(__name__)


@dataclass
class PaneTerminal:
    """Terminal state for a single pane.

    Wraps SlimScreen + pyte.Stream + action tracking.
    Handles stream data feeding and pattern matching.
    """

    pane_id: str
    screen: SlimScreen
    stream: pyte.Stream
    process: str = ""
    action: Action | None = None
    bytes_fed: int = 0
    bytes_since_watching: int = 0  # Track data received since WATCHING started
    last_accessed: float = 0.0  # Unix timestamp of last intentional access

    @classmethod
    def create(cls, pane_id: str, max_lines: int = 5000) -> "PaneTerminal":
        """Create a new PaneTerminal with initialized screen and stream.

        Args:
            pane_id: Pane identifier (e.g., "%123")
            max_lines: Maximum lines in ring buffer

        Returns:
            New PaneTerminal instance
        """
        screen = SlimScreen(max_lines=max_lines)
        # pyte.Stream uses duck typing - SlimScreen implements the interface
        stream = pyte.Stream(cast(pyte.Screen, screen))
        return cls(pane_id=pane_id, screen=screen, stream=stream)

    def feed(self, data: bytes) -> None:
        """Feed raw terminal data through pyte.

        Args:
            data: Raw bytes from tmux pipe-pane

        Decodes UTF-8 with replacement for invalid bytes,
        then feeds through pyte.Stream to update screen.
        """
        self.bytes_fed += len(data)
        try:
            text = data.decode("utf-8", errors="replace")
            logger.debug(f"Pane {self.pane_id} feeding {len(text)} chars to pyte")
            self.stream.feed(text)
        except Exception as e:
            logger.error(f"Pane {self.pane_id} pyte feed error: {e}")

    def check_patterns(self, patterns: PatternStore) -> str | None:
        """Check last N lines against patterns.

        Uses Pane abstraction which bundles content + process in sync.
        Falls back to tmux capture if stream has no data yet.

        Args:
            patterns: Pattern store to match against

        Returns:
            "ready" if terminal is ready for input
            "busy" if terminal is busy
            None if no pattern matches (unknown state)
        """
        from ..pane import Pane

        if self.bytes_fed == 0:
            # Stream empty, use tmux capture (last 10 lines for pattern matching)
            pane = Pane.capture_tail(self.pane_id, 10)
        else:
            # Use stream buffer
            pane = Pane.from_stream(self, n=10)

        # Update cached process
        self.process = pane.process

        return patterns.match(pane.process, pane.content)
