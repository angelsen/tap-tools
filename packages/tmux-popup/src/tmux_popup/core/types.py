"""Type definitions for tmux-popup v3.

PUBLIC API:
  - Dimension: Type alias for size specifications (int or percent string)
  - BorderStyle: Type alias for border style literals
  - Align: Type alias for text alignment literals
  - TimeoutResult: Sentinel class for timed-out interactive operations
  - CancelledResult: Sentinel class for cancelled interactive operations
"""

from typing import Union, Literal


# Type aliases for dimensions and styles
Dimension = Union[int, str]  # 50 or "50%"
BorderStyle = Literal["none", "normal", "rounded", "thick", "double", "hidden"]
Align = Literal["left", "center", "right"]


class TimeoutResult:
    """Returned when an interactive operation times out.

    This is a sentinel value that evaluates to False in boolean context.
    """

    def __repr__(self) -> str:
        return "TimeoutResult()"

    def __bool__(self) -> bool:
        return False

    def __str__(self) -> str:
        return "Operation timed out"


class CancelledResult:
    """Returned when user cancels an interactive operation (e.g., Ctrl+C).

    This is a sentinel value that evaluates to False in boolean context.
    """

    def __repr__(self) -> str:
        return "CancelledResult()"

    def __bool__(self) -> bool:
        return False

    def __str__(self) -> str:
        return "Operation cancelled by user"
