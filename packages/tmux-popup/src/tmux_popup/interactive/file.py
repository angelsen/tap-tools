"""File and directory picker.

PUBLIC API:
  - FilePicker: Interactive file and directory selection interface
"""

from dataclasses import dataclass
from typing import Dict, Tuple, Any, List
from ..core.base import Interactive


@dataclass
class FilePicker(Interactive):
    """Interactive file and directory selection interface.

    All passthrough except path handling.

    Attributes:
        path: Starting directory path.
        gum_args: Additional gum command line flags.
    """

    _gum_command = "file"
    _needs_tty = True
    _capture_output = True

    path: str = "."

    def __init__(self, path=".", **gum_args):
        """Initialize FilePicker with starting path and gum arguments.

        Args:
            path: Starting directory path.
            **gum_args: All gum flags for file picker configuration.
        """
        self.path = path
        self.gum_args = gum_args

    def _prepare_data(self) -> Tuple[List[str], Dict[str, Any]]:
        """Add path argument."""
        return [self.path], {}

    def _parse_result(self, raw: str, exit_code: int, hints: Dict) -> str:
        """Return the selected file path."""
        return raw.strip()
