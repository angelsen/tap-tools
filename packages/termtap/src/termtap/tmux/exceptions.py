"""tmux module exceptions."""


class TmuxError(Exception):
    """Base exception for tmux operations."""
    pass


class TmuxNotAvailableError(TmuxError):
    """Raised when tmux is not installed or server not running."""
    pass


class SessionError(TmuxError):
    """Base exception for session operations."""
    pass


class SessionNotFoundError(SessionError):
    """Raised when target session doesn't exist."""
    pass


class SessionAlreadyExistsError(SessionError):
    """Raised when trying to create a session with existing name."""
    pass


class CurrentPaneError(SessionError):
    """Raised when attempting operations on current pane."""
    pass


class PaneError(TmuxError):
    """Base exception for pane operations."""
    pass


class PaneCaptureError(PaneError):
    """Raised when failing to capture pane output."""
    pass


class StreamError(TmuxError):
    """Base exception for streaming operations."""
    pass


class StreamIOError(StreamError):
    """Raised on file I/O errors in stream operations."""
    pass


class ParseError(TmuxError):
    """Raised when failing to parse tmux output."""
    pass