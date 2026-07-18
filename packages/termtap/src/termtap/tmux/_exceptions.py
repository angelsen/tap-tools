"""Tmux-specific exceptions."""


class TmuxError(Exception):
    """Base exception for all tmux operations."""

    pass


class CurrentPaneError(TmuxError):
    """Raised when attempting forbidden operations on current pane."""

    pass


class PaneNotFoundError(TmuxError):
    """Raised when a tmux pane cannot be found."""

    pass
