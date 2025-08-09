"""Tmux popup system for rich terminal UIs.

PUBLIC API:
  - Popup: Main popup runner for tmux display-popup
  - Command: Base class for popup commands
"""

import subprocess
import tempfile
from pathlib import Path
from typing import Any, List, Optional, Union


class Command:
    """Base class for popup commands.

    All commands must implement render() to produce shell script lines.
    Commands that return values should set returns=True.
    """

    def __init__(self, returns: bool = False):
        """Initialize command.

        Args:
            returns: Whether this command returns a value.
        """
        self.returns = returns
        self._result_file: Optional[Path] = None

    def render(self) -> List[str]:
        """Render command to shell script lines.

        Returns:
            List of shell script lines to execute.
        """
        raise NotImplementedError

    def set_result_file(self, path: Path) -> None:
        """Set result file path for commands that return values.

        Args:
            path: Path to result file.
        """
        self._result_file = path

    def parse_result(self, content: str) -> Any:
        """Parse result from output file.

        Args:
            content: Raw content from result file.

        Returns:
            Parsed result (command-specific).
        """
        return content.strip()


class Popup:
    """Tmux popup runner using display-popup.

    Provides composable interface for building and executing popup scripts.
    Supports any Command objects that render to shell script lines.
    """

    def __init__(
        self,
        width: Optional[str] = None,
        height: Optional[str] = None,
        title: Optional[str] = None,
    ):
        """Initialize popup.

        Args:
            width: Popup width (percentage or characters).
            height: Popup height (percentage or lines).
            title: Window title for tmux popup.
        """
        self.width = width
        self.height = height
        self.title = title
        self._commands: List[Union[Command, str]] = []
        self._cleanup_files: List[Path] = []

    def add(self, *items: Union[Command, str]) -> "Popup":
        """Add commands or raw lines to popup.

        Args:
            *items: Command objects or raw shell strings.

        Returns:
            Self for chaining.
        """
        self._commands.extend(items)
        return self

    def show(self) -> Any:
        """Execute popup and return result if any.

        Returns:
            Result from last command if it returns a value, None otherwise.
        """
        if not self._commands:
            return None

        # Find the returning command (usually the last interactive one)
        returning_command = None
        result_file = None

        for cmd in reversed(self._commands):
            if isinstance(cmd, Command) and cmd.returns:
                returning_command = cmd
                result_file = self._create_temp_file(suffix=".result")
                cmd.set_result_file(result_file)
                break

        # Build script
        script_lines = ["#!/bin/bash"]
        for item in self._commands:
            if isinstance(item, Command):
                script_lines.extend(item.render())
            elif item == "":  # Empty string = spacer
                script_lines.append("echo ''")
            else:  # Raw shell command or text
                if not item.startswith(("echo", "read", "if", "gum")):
                    # Plain text - echo it
                    script_lines.append(f"echo {_quote(item)}")
                else:
                    # Shell command - add as-is
                    script_lines.append(item)

        # Execute
        result = self._execute_popup(script_lines)

        # Parse result if we have a returning command
        if returning_command and result_file and result_file.exists():
            content = result_file.read_text()
            result = returning_command.parse_result(content)
        else:
            result = None

        # Cleanup
        self._cleanup()

        return result

    def _create_temp_file(self, suffix: str = ".tmp", content: str = "") -> Path:
        """Create temporary file tracked for cleanup.

        Args:
            suffix: File suffix.
            content: Initial content.

        Returns:
            Path to temp file.
        """
        temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False)
        if content:
            temp_file.write(content)
        temp_file.close()

        path = Path(temp_file.name)
        self._cleanup_files.append(path)
        return path

    def _execute_popup(self, script_lines: List[str]) -> None:
        """Execute script in tmux display-popup.

        Args:
            script_lines: Shell script lines to execute.
        """
        # Create script file
        script_file = self._create_temp_file(suffix=".sh")
        script_file.write_text("\n".join(script_lines))
        script_file.chmod(0o755)

        # Build tmux command
        popup_cmd = ["tmux", "display-popup"]
        if self.width:
            popup_cmd.extend(["-w", self.width])
        if self.height:
            popup_cmd.extend(["-h", self.height])
        if self.title:
            popup_cmd.extend(["-T", self.title])
        popup_cmd.extend(["-E", str(script_file)])

        # Execute
        subprocess.run(popup_cmd, check=False)

    def _cleanup(self) -> None:
        """Clean up temporary files."""
        for path in self._cleanup_files:
            if path.exists():
                path.unlink()
        self._cleanup_files.clear()

    def __enter__(self) -> "Popup":
        """Context manager entry."""
        return self

    def __exit__(self, *args) -> None:
        """Context manager exit with cleanup."""
        self._cleanup()


def _quote(text: str) -> str:
    """Quote text for shell safety.

    Args:
        text: Text to quote.
    """
    import shlex

    return shlex.quote(text)
