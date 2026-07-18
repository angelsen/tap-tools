"""UI package for termtap companion.

PUBLIC API:
  - TermtapCompanion: Main companion app
  - run_companion: Entry point for companion app
"""

from .companion import TermtapCompanion, run_companion

__all__ = ["TermtapCompanion", "run_companion"]
