"""Pager command for gum (scrollable content viewer)."""

from typing import Optional
from .base import _DisplayCommand, _TimeoutMixin


class GumPager(_DisplayCommand, _TimeoutMixin):
    """Scrollable content viewer."""

    def __init__(
        self,
        content: str,
        show_line_numbers: bool = False,
        soft_wrap: bool = True,
        timeout: Optional[int] = None,
    ):
        """Initialize pager.

        Args:
            content: Content to display.
            show_line_numbers: Show line numbers.
            soft_wrap: Wrap long lines.
            timeout: Timeout in seconds.
        """
        super().__init__("pager")
        self.content = content
        self.show_line_numbers = show_line_numbers
        self.soft_wrap = soft_wrap
        self.timeout = timeout

    def render(self) -> list[str]:
        """Render pager command."""
        args = self.build_base_cmd()

        # Pager-specific args
        if self.show_line_numbers:
            args.append("--show-line-numbers")

        if not self.soft_wrap:
            args.append("--no-soft-wrap")

        self.add_timeout_arg(args)

        # Use echo to pipe content
        return [f"echo {self.quote(self.content)} | {' '.join(args)}"]
