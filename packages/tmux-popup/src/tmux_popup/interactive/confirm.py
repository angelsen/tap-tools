"""Yes/no confirmation dialog.

PUBLIC API:
  - Confirm: Interactive confirmation dialog with customizable buttons and defaults
"""

from dataclasses import dataclass
from typing import Optional, Any
from ..core.base import Interactive


@dataclass
class Confirm(Interactive):
    """Ask user to confirm an action with yes/no dialog.

    Returns True for yes/affirmative, False for no/negative.
    Uses exit codes: 0 for yes, 1 for no.
    """

    _gum_command = "confirm"
    _needs_tty = True
    _capture_output = False  # Uses exit code instead of stdout
    _use_exit_code = True

    # Core data
    prompt: Optional[str] = None

    def __init__(self, prompt: Optional[str] = None, **gum_args: Any):
        """Initialize Confirm with prompt and passthrough args.

        Args:
            prompt: Question to ask the user
            **gum_args: All gum flags

        Common gum_args:
            default: Default action (True for yes, False for no)
            affirmative: Text for yes button (default "Yes")
            negative: Text for no button (default "No")
            timeout: Timeout in seconds (e.g., "10s")
            show_output: Print prompt and choice to output
        """
        self.prompt = prompt
        self.gum_args = gum_args
        # Initialize base class storage
        self._parse_hints = {}

    def _prepare_data(self) -> tuple[list[str], dict[str, Any]]:
        """Prepare the confirm command.

        The prompt is passed as a positional argument.
        """
        args: list[str] = []

        # Add prompt as positional argument if provided
        if self.prompt:
            args.append(self.prompt)

        # No parse hints needed for confirm
        self._parse_hints = {}

        return args, self._parse_hints

    def _parse_result(self, raw: str, exit_code: int, hints: dict[str, Any]) -> bool:
        """Parse the result from exit code.

        The builder converts exit code to "true"/"false" string.

        Returns:
            True if user confirmed (yes/affirmative)
            False if user declined (no/negative)
        """
        # The builder converts exit code 0 to "true", non-zero to "false"
        return raw.strip().lower() == "true"
