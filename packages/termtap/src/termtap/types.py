"""Type definitions for termtap daemon architecture.

PUBLIC API:
  - LineEnding: Line ending types for command execution
"""

from enum import StrEnum

__all__ = ["LineEnding"]


class LineEnding(StrEnum):
    """Line ending types for command execution.

    Used to specify how commands should be terminated when sent to panes.
    Supports different operating systems and terminal types.
    """

    LF = "lf"  # Unix/Linux line feed (\n) - default
    CRLF = "crlf"  # Windows carriage return + line feed (\r\n)
    CR = "cr"  # Old Mac/some terminals carriage return (\r)
    NONE = ""  # No line ending
