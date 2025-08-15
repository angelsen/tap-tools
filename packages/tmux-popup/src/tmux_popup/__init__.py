"""Hybrid Python Data API with full gum passthrough for tmux popups.

A minimal, data-focused wrapper for tmux popups using gum.
Handles Python data structures excellently while allowing full gum compatibility
through passthrough for all other flags.

PUBLIC API:
  - Popup: Main container for displaying elements in tmux popups
  - Canvas: Container for content elements with layout management
  - Row: Horizontal layout container for organizing elements
  - Column: Vertical layout container for organizing elements
  - Text: Plain text content element
  - Markdown: Formatted markdown content
  - Choose: Interactive selection from a list of options
  - Filter: Interactive fuzzy search and filtering
  - Input: Single-line text input
  - Write: Multi-line text input
  - Confirm: Yes/no confirmation dialog
  - Table: Tabular data display and selection
  - FilePicker: File and directory selection
  - Pager: Scrollable text display
  - Spin: Loading spinner with background task
  - Format: Text formatting and styling
  - TimeoutResult: Sentinel value for timed-out operations
  - CancelledResult: Sentinel value for cancelled operations
  - Dimension: Type alias for size specifications
  - BorderStyle: Type alias for border styles
  - Align: Type alias for alignment options
"""

__version__ = "3.0.0"

# Core
from .popup import Popup
from .canvas import Canvas

# Layout elements
from .layout import Row, Column

# Content elements for Canvas
from .content import Text, Markdown

# Interactive elements
from .interactive import (
    Choose,
    Filter,
    Input,
    Write,
    Confirm,
    Table,
    FilePicker,
    Pager,
    Spin,
    Format,
)

# Types for type hints
from .core.types import (
    TimeoutResult,
    CancelledResult,
    Dimension,
    BorderStyle,
    Align,
)

__all__ = [
    # Core
    "Popup",
    "Canvas",
    # Layout
    "Row",
    "Column",
    # Content
    "Text",
    "Markdown",
    # Interactive
    "Choose",
    "Filter",
    "Input",
    "Write",
    "Confirm",
    "Table",
    "FilePicker",
    "Pager",
    "Spin",
    "Format",
    # Types
    "TimeoutResult",
    "CancelledResult",
    "Dimension",
    "BorderStyle",
    "Align",
]
