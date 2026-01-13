"""Target resolution - resolve target string to pane_id.

PUBLIC API:
  - resolve_target: Resolve target to pane_id
"""

from .core import run_tmux, _get_pane_id

__all__ = ["resolve_target"]


def resolve_target(target: str) -> str | None:
    """Resolve target string to pane_id.

    Supports:
    - Pane ID directly (%42)
    - Session:window.pane (dev:0.0)
    - Session name (dev) -> first pane
    - Session:window (dev:0) -> first pane in window

    Args:
        target: Target identifier

    Returns:
        Pane ID or None if not found
    """
    target = target.strip()

    # Direct pane ID
    if target.startswith("%"):
        # Verify it exists
        code, _, _ = run_tmux(["list-panes", "-t", target, "-F", "#{pane_id}"])
        return target if code == 0 else None

    # Parse session:window.pane format
    session = target
    window = "0"
    pane = "0"

    if ":" in target:
        parts = target.split(":", 1)
        session = parts[0]
        rest = parts[1] if len(parts) > 1 else "0"

        if "." in rest:
            wp = rest.split(".", 1)
            window = wp[0] or "0"
            pane = wp[1] or "0"
        else:
            window = rest or "0"
            pane = "0"

    return _get_pane_id(session, window, pane)
