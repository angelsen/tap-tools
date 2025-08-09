"""Gum-based popup commands for rich terminal UIs.

PUBLIC API:
  Selection Commands:
    - GumChoose: Select from list
    - GumFilter: Fuzzy search selection
    - GumFile: File/directory picker
    - GumTable: Table row selection

  Input Commands:
    - GumInput: Single-line text input
    - GumWrite: Multi-line text input
    - GumConfirm: Yes/no confirmation

  Display Commands:
    - GumStyle: Styled text output
    - GumFormat: Format text (markdown/emoji/code)
    - GumLog: Structured logging
    - GumPager: Scrollable content viewer

  Layout Commands:
    - GumJoin: Join text horizontally/vertically

  Process Commands:
    - GumSpin: Execute with spinner
"""

# Selection commands
from .selection import GumChoose, GumFilter, GumFile, GumTable

# Input commands
from .input import GumInput, GumWrite
from .confirm import GumConfirm

# Display commands
from .display import GumStyle, GumFormat, GumLog
from .pager import GumPager

# Layout commands
from .layout import GumJoin

# Process commands
from .spin import GumSpin

__all__ = [
    # Selection
    "GumChoose",
    "GumFilter",
    "GumFile",
    "GumTable",
    # Input
    "GumInput",
    "GumWrite",
    "GumConfirm",
    # Display
    "GumStyle",
    "GumFormat",
    "GumLog",
    "GumPager",
    # Layout
    "GumJoin",
    # Process
    "GumSpin",
]
