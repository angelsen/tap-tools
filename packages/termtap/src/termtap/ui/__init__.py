"""UI package for termtap companion.

PUBLIC API:
  - TermtapCompanion: Main companion app
  - run_companion: Entry point for companion app
  - show_popup: Launch companion in tmux popup
"""

from .companion import TermtapCompanion, run_companion
from .popup import show_popup

__all__ = ["TermtapCompanion", "run_companion", "show_popup"]
