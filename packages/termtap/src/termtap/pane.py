"""Unified pane abstraction - bundles content + process in sync.

PUBLIC API:
  - Pane: Unified pane data with content + process
"""

from dataclasses import dataclass

from .tmux.ops import get_pane, capture_visible, capture_last_n
from .tmux.core import run_tmux

__all__ = ["Pane"]


@dataclass
class Pane:
    """Unified pane data with content + process.

    Abstraction layer that:
    - Bundles content + process (always in sync)
    - Supports range/offset for paging
    - Abstracts underlying source (tmux today, could swap later)
    - Stream variant with clear-based capture (no race conditions)
    """

    pane_id: str  # Always %id format
    content: str  # Lines of text
    process: str  # Current process (fresh from tmux)
    total_lines: int  # Total lines in buffer
    range: tuple[int, int]  # (start, end) line numbers returned

    # --- Capture constructors ---

    @classmethod
    def capture(cls, pane_id: str) -> "Pane":
        """Capture visible content.

        Args:
            pane_id: Pane ID (%id format)

        Returns:
            Pane with visible content
        """
        info = get_pane(pane_id)
        content = capture_visible(pane_id)
        lines = content.splitlines() if content else []
        return cls(
            pane_id=pane_id,
            content=content,
            process=info.pane_current_command if info else "unknown",
            total_lines=len(lines),
            range=(0, len(lines)),
        )

    @classmethod
    def capture_tail(cls, pane_id: str, n: int) -> "Pane":
        """Capture last N lines.

        Args:
            pane_id: Pane ID (%id format)
            n: Number of lines to capture

        Returns:
            Pane with last N lines
        """
        info = get_pane(pane_id)
        content = capture_last_n(pane_id, n)
        lines = content.splitlines() if content else []
        total = cls._get_total_lines(pane_id)
        start = max(0, total - len(lines))
        return cls(
            pane_id=pane_id,
            content=content,
            process=info.pane_current_command if info else "unknown",
            total_lines=total,
            range=(start, total),
        )

    @classmethod
    def capture_range(cls, pane_id: str, offset: int, limit: int) -> "Pane":
        """Capture specific range for paging.

        Args:
            pane_id: Pane ID (%id format)
            offset: Starting line number (0-indexed)
            limit: Number of lines to capture

        Returns:
            Pane with specified range
        """
        # Use tmux capture-pane with -S (start) and -E (end) flags
        # tmux uses negative numbers for history (-1 = last line, -2 = second last, etc.)
        # Convert our 0-indexed offset to tmux's negative indexing
        total = cls._get_total_lines(pane_id)

        # Calculate tmux start/end (negative from end)
        start_tmux = -(total - offset)
        end_tmux = -(total - offset - limit)

        code, stdout, _ = run_tmux(["capture-pane", "-t", pane_id, "-p", "-S", str(start_tmux), "-E", str(end_tmux)])

        content = stdout.strip() if code == 0 else ""
        info = get_pane(pane_id)

        lines = content.splitlines() if content else []
        return cls(
            pane_id=pane_id,
            content=content,
            process=info.pane_current_command if info else "unknown",
            total_lines=total,
            range=(offset, offset + len(lines)),
        )

    # --- Stream constructors ---

    @classmethod
    def from_stream(cls, terminal, n: int = 10) -> "Pane":
        """From stream buffer, last N lines.

        Args:
            terminal: PaneTerminal instance
            n: Number of lines to get

        Returns:
            Pane with last N lines from stream
        """
        info = get_pane(terminal.pane_id)
        content = terminal.screen.last_n_lines(n)
        total = terminal.screen.line_count
        return cls(
            pane_id=terminal.pane_id,
            content=content,
            process=info.pane_current_command if info else "unknown",
            total_lines=total,
            range=(max(0, total - n), total),
        )

    @classmethod
    def from_stream_all(cls, terminal) -> "Pane":
        """All content from stream buffer (for execute output).

        Args:
            terminal: PaneTerminal instance

        Returns:
            Pane with all buffer content
        """
        info = get_pane(terminal.pane_id)
        content = terminal.screen.all_content()
        total = terminal.screen.line_count

        return cls(
            pane_id=terminal.pane_id,
            content=content,
            process=info.pane_current_command if info else "unknown",
            total_lines=total,
            range=(0, total),
        )

    # --- Helpers ---

    @staticmethod
    def _get_total_lines(pane_id: str) -> int:
        """Get total line count in pane history.

        Uses tmux display-message to get history size.
        """
        code, stdout, _ = run_tmux(["display-message", "-p", "-t", pane_id, "#{history_size}"])
        if code == 0:
            try:
                return int(stdout.strip())
            except ValueError:
                pass
        return 0
