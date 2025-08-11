"""Spin command for gum (command with spinner)."""

from typing import Optional
from .base import _DisplayCommand, _TimeoutMixin


class GumSpin(_DisplayCommand, _TimeoutMixin):
    """Execute command with spinner animation."""

    def __init__(
        self,
        command: str,
        title: str = "Loading...",
        spinner: str = "dot",
        show_output: bool = False,
        show_error: bool = True,
        align: str = "left",
        timeout: Optional[int] = None,
    ):
        """Initialize spin command.

        Args:
            command: Command to execute.
            title: Text to display while spinning.
            spinner: Spinner type (dot, line, minidot, jump, pulse, points, etc).
            show_output: Show command output during execution.
            show_error: Show output only on error.
            align: Alignment of spinner with title.
            timeout: Timeout in seconds.
        """
        super().__init__("spin")
        self.command = command
        self.title = title
        self.spinner = spinner
        self.show_output = show_output
        self.show_error = show_error
        self.align = align
        self.timeout = timeout

    def render(self) -> list[str]:
        """Render spin command."""
        args = self.build_base_cmd()

        # Spin-specific args
        args.extend(["--title", self.quote(self.title)])
        args.extend(["--spinner", self.spinner])

        if self.show_output:
            args.append("--show-output")
        elif self.show_error:
            args.append("--show-error")

        if self.align != "left":
            args.extend(["--align", self.align])

        self.add_timeout_arg(args)

        # Add the command to execute
        args.append("--")
        args.append(self.command)

        return [" ".join(args)]
