"""Popup integration for termtap companion.

PUBLIC API:
  - show_popup: Launch companion in tmux popup
"""

from ..tmux.core import run_tmux

__all__ = ["show_popup"]


def show_popup(session: str | None = None):
    """Launch companion app in tmux popup.

    Args:
        session: Session to show popup in. Uses current if None.
    """
    cmd = ["display-popup", "-E", "termtap companion --popup"]

    if session:
        cmd.insert(1, "-t")
        cmd.insert(2, session)

    run_tmux(cmd)


def trigger_popup_if_needed(pane_id: str):
    """Trigger popup if configured and no companion connected.

    Args:
        pane_id: Pane that needs interaction
    """
    from ..config import load_config

    config = load_config()

    if config.ui_mode != "popup":
        return

    # Get session from pane_id
    code, out, _ = run_tmux(["display", "-t", pane_id, "-p", "#{session_name}"])
    if code == 0:
        session = out.strip()
        show_popup(session)
