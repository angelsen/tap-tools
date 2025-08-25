"""Loading spinner with command execution.

PUBLIC API:
  - Spin: Interactive spinner that shows progress while executing background commands
"""

from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Any
from ..core.base import Interactive


@dataclass
class Spin(Interactive):
    """Interactive spinner that shows progress while executing background commands.

    Shows a spinner animation while running a command in the background.

    Attributes:
        command: Command to execute as list of arguments.
        gum_args: Additional gum command line flags.
    """

    _gum_command = "spin"
    _needs_tty = False  # Can use pipes
    _capture_output = True

    command: List[str] = field(default_factory=list)

    def __init__(self, command, **gum_args):
        """Initialize Spin with command and gum arguments.

        Args:
            command: Command to execute (string or list of arguments).
            **gum_args: All gum flags for spinner configuration.
        """
        if isinstance(command, str):
            # Convert string command to list
            import shlex

            self.command = shlex.split(command)
        else:
            self.command = command
        self.gum_args = gum_args

    def _prepare_data(self) -> Tuple[List[str], Dict[str, Any]]:
        """Add command to execute."""
        # The command comes after all flags in gum spin
        return self.command, {}

    def _parse_result(self, raw: str, exit_code: int, hints: Dict) -> str:
        """Return command output."""
        return raw
