"""Scrollable content viewer.

PUBLIC API:
  - Pager: Interactive pager for scrolling through long text content
"""

from dataclasses import dataclass
from typing import Optional, Dict, Tuple, Any, List
from ..core.base import Interactive


@dataclass
class Pager(Interactive):
    """Pager for scrollable content viewing."""

    _gum_command = "pager"
    _needs_tty = True
    _capture_output = False  # Pager doesn't return anything

    content: Optional[str] = None

    def __init__(self, content=None, **gum_args):
        """Initialize Pager with content and passthrough."""
        self.content = content
        self.gum_args = gum_args

    def _prepare_data(self) -> Tuple[List[str], Dict[str, Any]]:
        """Prepare content for pager."""
        args = []
        hints = {}

        if self.content:
            # Content will be piped via stdin
            hints["stdin_data"] = self.content

        return args, hints

    def _parse_result(self, raw: str, exit_code: int, hints: Dict) -> None:
        """Pager doesn't return anything."""
        return None
