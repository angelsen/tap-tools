"""Base classes for tmux-popup v3.

PUBLIC API:
  - Element: Abstract base class for all UI elements
  - Interactive: Base class for interactive gum elements with data handling
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple, Optional, TYPE_CHECKING
from abc import ABC, abstractmethod

if TYPE_CHECKING:
    from .builder import ShellBuilder


@dataclass
class Element(ABC):
    """Base class for all UI elements.

    Elements are the building blocks of tmux-popup. They can be:
    - Layout elements (Row, Column)
    - Content elements (Text, Markdown, Code)
    - Interactive elements (Input, Choose, etc.)
    - Container elements (Canvas)
    """

    @abstractmethod
    def render(self, builder: "ShellBuilder") -> str:
        """Render element to shell commands.

        Args:
            builder: Shell script builder

        Returns:
            Variable name containing the rendered content
        """
        pass

    def render_with_allocation(
        self, builder: "ShellBuilder", allocated_width: Optional[str] = None, allocated_height: Optional[str] = None
    ) -> str:
        """Render element with allocated dimensions from parent.

        This is used by layout elements to tell children their available space.
        Default implementation ignores allocation and calls render().

        Args:
            builder: Shell script builder
            allocated_width: Width allocated by parent (can be shell variable like "$WIDTH")
            allocated_height: Height allocated by parent

        Returns:
            Variable name containing the rendered content
        """
        return self.render(builder)

    def render_with_style(self, builder: "ShellBuilder", available_width: Optional[str] = None) -> str:
        """Render element with styling for simple canvas mode.

        This is used by content elements (Text, Markdown, Code) when placed
        directly in a canvas without explicit layout.
        Default implementation ignores styling and calls render().

        Args:
            builder: Shell script builder
            available_width: Available width from parent

        Returns:
            Variable name containing the rendered content
        """
        return self.render(builder)


@dataclass
class Interactive(Element):
    """Base class for interactive gum elements.

    Interactive elements handle:
    - Data conversion (Python -> gum command)
    - Command building with passthrough args
    - Result parsing (gum output -> Python)
    """

    # Storage for gum flags not directly handled by the subclass
    gum_args: Dict[str, Any] = field(default_factory=dict)

    # Configuration attributes set by subclasses
    _gum_command: str = ""  # The gum subcommand (e.g., "choose", "input")
    _needs_tty: bool = False  # Whether command requires direct TTY access
    _capture_output: bool = True  # Whether to capture output
    _use_exit_code: bool = False  # Whether result comes from exit code
    _parse_hints: Dict[str, Any] = field(default_factory=dict)  # Hints for parsing results

    @abstractmethod
    def _prepare_data(self) -> Tuple[List[str], Dict[str, Any]]:
        """Prepare data for gum command.

        Subclasses implement this to convert Python data to gum arguments.

        Returns:
            Tuple of:
            - data_args: List of command arguments for the data
            - parse_hints: Dictionary of hints for parsing the result
        """
        pass

    @abstractmethod
    def _parse_result(self, raw: str, exit_code: int, hints: Dict[str, Any]) -> Any:
        """Parse gum output back to Python data.

        Subclasses implement this to convert gum output to Python objects.

        Args:
            raw: Raw output from gum command
            exit_code: Exit code from gum command
            hints: Parse hints from _prepare_data

        Returns:
            Parsed Python object (type depends on the element)
        """
        pass

    def _build_command(self) -> List[str]:
        """Build complete gum command with data and passthrough args.

        Combines:
        - Base gum command
        - Data arguments from _prepare_data
        - Passthrough arguments from gum_args

        Returns:
            Complete command as list of arguments
        """
        cmd = ["gum", self._gum_command]

        # Add data arguments
        data_args, self._parse_hints = self._prepare_data()
        cmd.extend(data_args)

        # Add passthrough arguments
        for key, value in self.gum_args.items():
            # Convert Python names to gum flags
            # Style flags use dots (cursor.foreground), others use hyphens
            if "." in key:
                # Style flag with dot notation
                flag = f"--{key}"
            else:
                # Regular flag, convert underscores to hyphens
                flag = f"--{key.replace('_', '-')}"

            if isinstance(value, bool):
                # Boolean flag
                if value:
                    cmd.append(flag)
            elif isinstance(value, list):
                # Repeated flag (e.g., --selected for multiple items)
                for item in value:
                    cmd.extend([flag, str(item)])
            elif value is None:
                # Skip None values
                continue
            else:
                # Regular flag with value
                cmd.extend([flag, str(value)])

        return cmd

    def render(self, builder: "ShellBuilder") -> str:
        """Render interactive element to shell commands.

        Args:
            builder: Shell script builder

        Returns:
            Variable name containing the result
        """
        cmd = self._build_command()
        return builder.add_interactive(self, cmd)

    def parse_result(self, raw: str, exit_code: int = 0) -> Any:
        """Parse the result from gum command.

        This is the public parsing method that handles special cases
        like timeouts and cancellations.

        Args:
            raw: Raw output from gum command
            exit_code: Exit code from gum command

        Returns:
            Parsed result or special value (TimeoutResult, CancelledResult)
        """
        from .types import TimeoutResult, CancelledResult

        # Check for special cases
        if raw == "__TIMEOUT__":
            return TimeoutResult()
        if raw == "__CANCELLED__":
            return CancelledResult()

        # Delegate to subclass implementation
        return self._parse_result(raw, exit_code, self._parse_hints)
