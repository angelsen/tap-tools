"""Content formatting and styling.

PUBLIC API:
  - Format: Text formatting with support for markdown, templates, and code highlighting
"""

from dataclasses import dataclass
from typing import Dict, Tuple, Any, List
from ..core.base import Interactive


@dataclass
class Format(Interactive):
    """Format content using gum format."""

    _gum_command = "format"
    _needs_tty = False  # Can use pipes
    _capture_output = True

    content: str = ""
    format_type: str = "markdown"  # markdown, template, code, emoji

    def __init__(self, content, format_type="markdown", **gum_args):
        """Initialize Format with content and type."""
        self.content = content
        self.format_type = format_type
        self.gum_args = gum_args

    def _prepare_data(self) -> Tuple[List[str], Dict[str, Any]]:
        """Prepare format arguments."""
        args = ["--type", self.format_type]
        hints = {"stdin_data": self.content}
        return args, hints

    def _parse_result(self, raw: str, exit_code: int, hints: Dict) -> str:
        """Return formatted content."""
        return raw
