"""Base classes and mixins for gum commands."""

import shlex
from typing import Any, List, Optional
from .. import Command


# Mixins for shared functionality


class _StyleMixin:
    """Mixin for commands with style options."""

    def add_style_args(
        self, args: List[str], component: str, fg: Optional[str] = None, bg: Optional[str] = None
    ) -> None:
        """Add style arguments for a component.

        Args:
            args: Argument list to append to.
            component: Component name (e.g., "cursor", "header").
            fg: Foreground color.
            bg: Background color.
        """
        if fg is not None:
            args.extend([f"--{component}.foreground", str(fg)])
        if bg is not None:
            args.extend([f"--{component}.background", str(bg)])


class _HeaderMixin:
    """Mixin for commands with header option."""

    header: Optional[str]

    def add_header_arg(self, args: List[str]) -> None:
        """Add header argument if present.

        Args:
            args: Argument list to append to.
        """
        if hasattr(self, "header") and self.header:
            args.extend(["--header", shlex.quote(self.header)])


class _TimeoutMixin:
    """Mixin for commands with timeout option."""

    timeout: Optional[int]

    def add_timeout_arg(self, args: List[str]) -> None:
        """Add timeout argument if present.

        Args:
            args: Argument list to append to.
        """
        if hasattr(self, "timeout") and self.timeout is not None:
            args.extend(["--timeout", f"{self.timeout}s"])


class _ShowHelpMixin:
    """Mixin for commands with show-help option."""

    show_help: bool

    def add_show_help_arg(self, args: List[str]) -> None:
        """Add show-help argument.

        Args:
            args: Argument list to append to.
        """
        if hasattr(self, "show_help") and not self.show_help:
            args.append("--no-show-help")


# Base command classes


class _GumCommand(Command):
    """Base class for all gum commands."""

    def __init__(self, command: str, returns: bool = False):
        """Initialize gum command.

        Args:
            command: The gum subcommand name.
            returns: Whether this command returns a value.
        """
        super().__init__(returns=returns)
        self.command = command

    def quote(self, value: Any) -> str:
        """Quote value for shell safety.

        Args:
            value: Value to quote.

        Returns:
            Shell-quoted string.
        """
        return shlex.quote(str(value))

    def build_base_cmd(self) -> List[str]:
        """Build base gum command.

        Returns:
            Base command list.
        """
        return ["gum", self.command]


class _SelectionCommand(_GumCommand, _HeaderMixin, _TimeoutMixin, _ShowHelpMixin):
    """Base for commands that select from options."""

    def __init__(
        self,
        command: str,
        limit: int = 1,
        height: int = 10,
        header: Optional[str] = None,
        timeout: Optional[int] = None,
        show_help: bool = True,
    ):
        """Initialize selection command.

        Args:
            command: Gum subcommand name.
            limit: Maximum selections (1 for single, >1 for multi, 0 for unlimited).
            height: Display height.
            header: Optional header text.
            timeout: Timeout in seconds.
            show_help: Whether to show help keybinds.
        """
        super().__init__(command, returns=True)
        self.limit = limit
        self.height = height
        self.header = header
        self.timeout = timeout
        self.show_help = show_help

    def add_selection_args(self, args: List[str]) -> None:
        """Add selection-specific arguments.

        Args:
            args: Argument list to append to.
        """
        args.extend(["--height", str(self.height)])

        if self.limit == 0:
            args.append("--no-limit")
        elif self.limit > 1:
            args.extend(["--limit", str(self.limit)])
        # limit=1 is default, no arg needed

        self.add_header_arg(args)
        self.add_timeout_arg(args)
        self.add_show_help_arg(args)

    def parse_result(self, content: str) -> Any:
        """Parse selection result.

        Args:
            content: Raw result content.

        Returns:
            Single value if limit=1, list otherwise.
        """
        result = content.strip()

        if not result:
            return "" if self.limit == 1 else []

        if self.limit == 1:
            return result
        else:
            return result.split("\n")


class _InputCommand(_GumCommand, _HeaderMixin, _ShowHelpMixin):
    """Base for text input commands."""

    def __init__(
        self,
        command: str,
        placeholder: str = "",
        value: str = "",
        header: Optional[str] = None,
        char_limit: int = 0,
        show_help: bool = True,
    ):
        """Initialize input command.

        Args:
            command: Gum subcommand name.
            placeholder: Placeholder text.
            value: Initial value.
            header: Optional header text.
            char_limit: Maximum characters (0 for no limit).
            show_help: Whether to show help keybinds.
        """
        super().__init__(command, returns=True)
        self.placeholder = placeholder
        self.value = value
        self.header = header
        self.char_limit = char_limit
        self.show_help = show_help

    def add_input_args(self, args: List[str]) -> None:
        """Add input-specific arguments.

        Args:
            args: Argument list to append to.
        """
        if self.placeholder:
            args.extend(["--placeholder", self.quote(self.placeholder)])

        if self.value:
            args.extend(["--value", self.quote(self.value)])

        if self.char_limit > 0:
            args.extend(["--char-limit", str(self.char_limit)])

        self.add_header_arg(args)
        self.add_show_help_arg(args)

    def parse_result(self, content: str) -> str:
        """Parse input result.

        Args:
            content: Raw result content.

        Returns:
            User input string.
        """
        return content.strip()


class _DisplayCommand(_GumCommand):
    """Base for display-only commands."""

    def __init__(self, command: str):
        """Initialize display command."""
        super().__init__(command, returns=False)
