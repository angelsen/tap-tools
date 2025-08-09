"""Confirm command for gum (yes/no prompts)."""

from typing import Optional
from .base import _GumCommand


class GumConfirm(_GumCommand):
    """Yes/no confirmation prompt.

    Returns True for yes, False for no.
    """

    def __init__(
        self,
        prompt: str = "Continue?",
        default: bool = False,
        affirmative: str = "Yes",
        negative: str = "No",
        timeout: Optional[int] = None,
    ):
        """Initialize confirmation prompt.

        Args:
            prompt: Question to ask.
            default: Default choice if Enter pressed.
            affirmative: Text for yes option.
            negative: Text for no option.
            timeout: Timeout in seconds.
        """
        super().__init__("confirm", returns=True)
        self.prompt = prompt
        self.default = default
        self.affirmative = affirmative
        self.negative = negative
        self.timeout = timeout

    def render(self) -> list[str]:
        """Render confirm command."""
        args = self.build_base_cmd()

        # Add prompt
        args.append(self.quote(self.prompt))

        # Confirm-specific args
        args.extend(["--affirmative", self.quote(self.affirmative)])
        args.extend(["--negative", self.quote(self.negative)])

        if self.default:
            args.append("--default")

        if self.timeout is not None:
            args.extend(["--timeout", f"{self.timeout}s"])

        # Use exit code to determine result
        lines = []
        lines.append(f"if {' '.join(args)}; then")
        if self._result_file:
            lines.append(f"  echo 'true' > {self._result_file}")
        lines.append("else")
        if self._result_file:
            lines.append(f"  echo 'false' > {self._result_file}")
        lines.append("fi")

        return lines

    def parse_result(self, content: str) -> bool:
        """Parse confirmation result.

        Args:
            content: Raw result content.

        Returns:
            True if confirmed, False otherwise.
        """
        return content.strip() == "true"
