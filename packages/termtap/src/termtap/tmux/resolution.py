"""Pane ID validation - verify pane ID exists in tmux.

PUBLIC API:
  - validate_pane_id: Validate pane ID format and existence
"""

from .core import run_tmux

__all__ = ["validate_pane_id"]


def validate_pane_id(pane_id: str) -> str | None:
    """Validate pane ID exists.

    Args:
        pane_id: Must be %id format (e.g., "%42")

    Returns:
        pane_id if valid, None if not found or invalid format
    """
    if not pane_id.startswith("%"):
        return None
    code, _, _ = run_tmux(["list-panes", "-t", pane_id, "-F", "#{pane_id}"])
    return pane_id if code == 0 else None
