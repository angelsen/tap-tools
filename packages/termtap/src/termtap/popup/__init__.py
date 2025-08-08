"""Tmux-native popup system for termtap.

PUBLIC API:
  - Popup: Main popup builder class for complex interactions
  - Theme: Style theme for consistent popup appearance
  - quick_confirm: Quick confirmation dialog utility
  - quick_choice: Quick choice selection utility
  - quick_input: Quick input prompt utility
  - quick_info: Quick information display utility
"""

from termtap.popup.builder import (
    # Core classes
    Popup,
    Theme,
    # Convenience functions
    quick_confirm,
    quick_choice,
    quick_input,
    quick_info,
)

__all__ = [
    # Core
    "Popup",
    "Theme",
    # Quick dialogs
    "quick_confirm",
    "quick_choice",
    "quick_input",
    "quick_info",
]
