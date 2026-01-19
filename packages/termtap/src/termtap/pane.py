"""Unified pane abstraction - bundles content + process in sync.

PUBLIC API:
  - Pane: Unified pane data with content + process
"""

from dataclasses import dataclass

from .tmux.ops import get_pane, capture_pane

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
    def capture_tail(cls, pane_id: str, n: int) -> "Pane":
        """Capture last N lines (Python-side filtering).

        Args:
            pane_id: Pane ID (%id format)
            n: Number of lines to capture

        Returns:
            Pane with last N lines
        """
        info = get_pane(pane_id)
        all_content = capture_pane(pane_id)
        all_lines = all_content.splitlines() if all_content else []
        total = len(all_lines)

        # Get last N lines (Python filtering)
        tail_lines = all_lines[-n:] if len(all_lines) > n else all_lines
        content = "\n".join(tail_lines) + ("\n" if tail_lines else "")
        start = max(0, total - len(tail_lines))

        return cls(
            pane_id=pane_id,
            content=content,
            process=info.pane_current_command if info else "unknown",
            total_lines=total,
            range=(start, total),
        )

    @classmethod
    def capture_range(cls, pane_id: str, offset: int, limit: int) -> "Pane":
        """Capture specific range for paging (Python-side filtering).

        Args:
            pane_id: Pane ID (%id format)
            offset: Starting line number (0-indexed)
            limit: Number of lines to capture

        Returns:
            Pane with specified range
        """
        info = get_pane(pane_id)
        all_content = capture_pane(pane_id)
        all_lines = all_content.splitlines() if all_content else []
        total = len(all_lines)

        # Python-side slicing
        range_lines = all_lines[offset : offset + limit]
        content = "\n".join(range_lines) + ("\n" if range_lines else "")

        return cls(
            pane_id=pane_id,
            content=content,
            process=info.pane_current_command if info else "unknown",
            total_lines=total,
            range=(offset, offset + len(range_lines)),
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

    # --- Unified entry point ---

    # Default limit for capture fallback (when stream not available)
    _DEFAULT_CAPTURE_LIMIT = 100

    @classmethod
    def get(cls, pane_id: str, terminal=None, n: int | None = None) -> "Pane":
        """Unified retrieval - stream if available, capture if not.

        Encapsulates the stream-or-capture decision in one place.
        Use this instead of direct pane.screen access.

        Args:
            pane_id: Pane ID (%id format)
            terminal: PaneTerminal if available (for stream access)
            n: Number of lines (None = all stream content, or default limit for capture)

        Returns:
            Pane with content + process in sync
        """
        if terminal and terminal.bytes_fed > 0:
            return cls.from_stream_all(terminal) if n is None else cls.from_stream(terminal, n)
        else:
            limit = n if n is not None else cls._DEFAULT_CAPTURE_LIMIT
            return cls.capture_tail(pane_id, limit)

    # --- Helpers ---
