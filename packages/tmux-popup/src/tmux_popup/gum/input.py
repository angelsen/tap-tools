"""Input commands for gum (input, write)."""

from typing import Optional
from .base import _InputCommand


class GumInput(_InputCommand):
    """Single-line text input."""

    def __init__(
        self,
        placeholder: str = "Type something...",
        value: str = "",
        header: Optional[str] = None,
        prompt: str = "> ",
        width: int = 0,
        char_limit: int = 400,
        password: bool = False,
        timeout: Optional[int] = None,
        show_help: bool = True,
    ):
        """Initialize input command.

        Args:
            placeholder: Placeholder text when empty.
            value: Initial value.
            header: Optional header text.
            prompt: Prompt character(s).
            width: Input width (0 for terminal width).
            char_limit: Maximum character limit.
            password: Mask input for passwords.
            timeout: Timeout in seconds.
            show_help: Whether to show help keybinds.
        """
        super().__init__("input", placeholder, value, header, char_limit, show_help)
        self.prompt = prompt
        self.width = width
        self.password = password
        self.timeout = timeout

    def render(self) -> list[str]:
        """Render input command."""
        args = self.build_base_cmd()

        # Add base input args
        self.add_input_args(args)

        # Input-specific args
        args.extend(["--prompt", self.quote(self.prompt)])

        if self.width > 0:
            args.extend(["--width", str(self.width)])

        if self.password:
            args.append("--password")

        if self.timeout is not None:
            args.extend(["--timeout", f"{self.timeout}s"])

        if self._result_file:
            return [f"{' '.join(args)} > {self._result_file}"]
        else:
            return [" ".join(args)]


class GumWrite(_InputCommand):
    """Multi-line text input."""

    def __init__(
        self,
        placeholder: str = "Write something...",
        value: str = "",
        header: Optional[str] = None,
        width: int = 0,
        height: int = 5,
        char_limit: int = 0,
        max_lines: int = 0,
        show_line_numbers: bool = False,
        show_cursor_line: bool = False,
        timeout: Optional[int] = None,
        show_help: bool = True,
    ):
        """Initialize write command.

        Args:
            placeholder: Placeholder text when empty.
            value: Initial value.
            header: Optional header text.
            width: Text area width (0 for terminal width).
            height: Text area height.
            char_limit: Maximum character limit (0 for no limit).
            max_lines: Maximum number of lines (0 for no limit).
            show_line_numbers: Show line numbers.
            show_cursor_line: Highlight current line.
            timeout: Timeout in seconds.
            show_help: Whether to show help keybinds.
        """
        super().__init__("write", placeholder, value, header, char_limit, show_help)
        self.width = width
        self.height = height
        self.max_lines = max_lines
        self.show_line_numbers = show_line_numbers
        self.show_cursor_line = show_cursor_line
        self.timeout = timeout

    def render(self) -> list[str]:
        """Render write command."""
        args = self.build_base_cmd()

        # Add base input args
        self.add_input_args(args)

        # Write-specific args
        if self.width > 0:
            args.extend(["--width", str(self.width)])

        args.extend(["--height", str(self.height)])

        if self.max_lines > 0:
            args.extend(["--max-lines", str(self.max_lines)])

        if self.show_line_numbers:
            args.append("--show-line-numbers")

        if self.show_cursor_line:
            args.append("--show-cursor-line")

        if self.timeout is not None:
            args.extend(["--timeout", f"{self.timeout}s"])

        if self._result_file:
            return [f"{' '.join(args)} > {self._result_file}"]
        else:
            return [" ".join(args)]
