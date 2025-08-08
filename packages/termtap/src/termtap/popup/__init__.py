"""Tmux-native popup system for termtap.

True tmux display-popup implementation with gum.
Uses temp files for IPC between popup and Python process.
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
