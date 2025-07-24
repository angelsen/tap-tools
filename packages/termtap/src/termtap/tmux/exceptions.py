"""Exceptions for tmux operations.

This module defines exceptions that can be raised during tmux operations.
Only TmuxError, CurrentPaneError, and SessionNotFoundError are part of the
public API. All other exceptions are internal.
"""


class TmuxError(Exception):
    """Base exception for tmux operations."""

    pass


class _TmuxNotAvailableError(TmuxError):
    """Raised when tmux is not installed or server not running."""

    pass


class _SessionError(TmuxError):
    """Base exception for session operations."""

    pass


class SessionNotFoundError(_SessionError):
    """Raised when session doesn't exist."""

    pass


class _SessionAlreadyExistsError(_SessionError):
    """Raised when trying to create a session with existing name."""

    pass


class CurrentPaneError(_SessionError):
    """Raised when targeting current pane."""

    pass


class _PaneError(TmuxError):
    """Base exception for pane operations."""

    pass


class _PaneCaptureError(_PaneError):
    """Raised when failing to capture pane output."""

    pass


class _StreamError(TmuxError):
    """Base exception for streaming operations."""

    pass


class _StreamIOError(_StreamError):
    """Raised on file I/O errors in stream operations."""

    pass


class _ParseError(TmuxError):
    """Raised when failing to parse tmux output."""

    pass
