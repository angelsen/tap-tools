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
