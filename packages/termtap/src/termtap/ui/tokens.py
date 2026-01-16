"""Design tokens - Coloromatic colors only.

PUBLIC API:
  - COLOR_BG_DIM: Subtle backgrounds (Background dim mode)
  - COLOR_BG_BRIGHT: Active backgrounds (Background bright mode)
"""

__all__ = ["COLOR_BG_DIM", "COLOR_BG_BRIGHT"]

# Semantic colors - use Textual theme variables
COLOR_BG_DIM = ["$panel", "$surface"]  # Subtle backgrounds (Background dim mode)
COLOR_BG_BRIGHT = ["$primary", "$accent"]  # Active backgrounds (Background bright mode)
