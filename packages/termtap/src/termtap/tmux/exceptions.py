"""Tmux-specific exceptions.

PUBLIC API:
  - TmuxError: Base exception for all tmux operations
  - SessionNotFoundError: Session not found exception
  - CurrentPaneError: Current pane operation error
  - PaneNotFoundError: Pane not found exception
  - WindowNotFoundError: Window not found exception
"""


class TmuxError(Exception):
    """Base exception for all tmux operations."""

    pass


class SessionNotFoundError(TmuxError):
    """Raised when a tmux session cannot be found."""

    pass


class CurrentPaneError(TmuxError):
    """Raised when attempting forbidden operations on current pane."""

    pass


class PaneNotFoundError(TmuxError):
    """Raised when a tmux pane cannot be found."""

    pass


class WindowNotFoundError(TmuxError):
    """Raised when a tmux window cannot be found."""

    pass
