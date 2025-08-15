"""Text input commands with passthrough support.

PUBLIC API:
  - Input: Single-line text input with validation and styling
  - Write: Multi-line text editor with rich editing capabilities
"""

from dataclasses import dataclass
from typing import Dict, Tuple, Any, List
from ..core.base import Interactive


@dataclass
class Input(Interactive):
    """Input is pure passthrough - just returns string."""

    _gum_command = "input"
    _needs_tty = True
    _capture_output = True

    def __init__(self, **gum_args):
        """Initialize Input with passthrough only."""
        self.gum_args = gum_args

    def _prepare_data(self) -> Tuple[List[str], Dict[str, Any]]:
        """No data transformation needed."""
        return [], {}

    def _parse_result(self, raw: str, exit_code: int, hints: Dict) -> str:
        """Return the entered text."""
        return raw.strip()


@dataclass
class Write(Interactive):
    """Write is pure passthrough - returns multiline string."""

    _gum_command = "write"
    _needs_tty = True
    _capture_output = True

    def __init__(self, **gum_args):
        """Initialize Write with passthrough only."""
        self.gum_args = gum_args

    def _prepare_data(self) -> Tuple[List[str], Dict[str, Any]]:
        """No data transformation needed."""
        return [], {}

    def _parse_result(self, raw: str, exit_code: int, hints: Dict) -> str:
        """Return the entered text with newlines preserved."""
        return raw.rstrip()  # Preserve internal newlines
