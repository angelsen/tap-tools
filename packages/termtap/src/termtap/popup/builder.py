"""Tmux popup system using gum for rich terminal UIs.

PUBLIC API:
  - Popup: Main popup builder class
  - Theme: Style configuration for consistent appearance
  - quick_confirm: Simple confirmation dialog
  - quick_choice: Simple choice selection
  - quick_input: Simple text input
  - quick_info: Simple information display
"""

import os
import shlex
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple, Union


@dataclass
class Theme:
    """Style theme for consistent popup appearance.

    Provides predefined color and formatting combinations for different
    message types and UI elements in tmux popups.

    Attributes:
        header: Bold centered header styling.
        success: Green success message styling.
        warning: Yellow warning message styling.
        error: Red error message styling.
        info: Blue informational message styling.
        panel: Panel border and padding styling.
        accent: Highlighted accent text styling.
        faint: Dimmed secondary text styling.
    """

    header: str = "--bold --foreground 14 --border rounded --align center"
    success: str = "--foreground 10"
    warning: str = "--foreground 11 --bold"
    error: str = "--foreground 9 --bold"
    info: str = "--foreground 12"
    panel: str = "--border rounded --padding 1"
    accent: str = "--foreground 14 --bold"
    faint: str = "--foreground 8 --faint"


class Popup:
    """Tmux-native popup builder using display-popup and gum.

    Provides a fluent interface for building rich terminal popups with
    interactive components. Supports text display, user input, choices,
    tables, and confirmation dialogs.

    Attributes:
        theme: Styling configuration for consistent appearance.
        width: Popup width specification.
        height: Popup height specification.
        title: Window title for the popup.
    """

    def __init__(
        self,
        theme: Optional[Theme] = None,
        width: Optional[str] = None,
        height: Optional[str] = None,
        title: Optional[str] = None,
    ):
        """Initialize popup builder with optional configuration.

        Args:
            theme: Style theme for consistent appearance. Defaults to None.
            width: Popup width (percentage or characters). Defaults to None.
            height: Popup height (percentage or lines). Defaults to None.
            title: Window title for tmux popup. Defaults to None.
        """
        self.theme = theme or Theme()
        self.width = width
        self.height = height
        self.title = title
        self._script_lines: List[str] = []
        self._result_file: Optional[Path] = None
        self._cleanup_files: List[Path] = []

    def _add_line(self, line: str) -> "Popup":
        """Add a line to the popup script."""
        self._script_lines.append(line)
        return self

    def _add_gum_style(self, text: str, style: str) -> "Popup":
        """Add a gum style command to display styled text."""
        escaped_text = shlex.quote(text)
        style_args = shlex.split(style)
        style_cmd = " ".join(shlex.quote(arg) for arg in style_args)
        self._add_line(f"gum style {escaped_text} {style_cmd}")
        return self

    def header(self, text: str) -> "Popup":
        """Add styled header."""
        self._add_gum_style(text, getattr(self.theme, "header", ""))
        self._add_line("")
        return self

    def text(self, content: str, style: Optional[str] = None) -> "Popup":
        """Add plain or styled text."""
        if style:
            self._add_gum_style(content, style)
        else:
            self._add_line(f"echo {shlex.quote(content)}")
        return self

    def info(self, text: str) -> "Popup":
        """Add info message."""
        self._add_gum_style(text, getattr(self.theme, "info", ""))
        return self

    def success(self, text: str) -> "Popup":
        """Add success message."""
        self._add_gum_style(text, getattr(self.theme, "success", ""))
        return self

    def warning(self, text: str) -> "Popup":
        """Add warning message."""
        self._add_gum_style(text, getattr(self.theme, "warning", ""))
        return self

    def error(self, text: str) -> "Popup":
        """Add error message."""
        self._add_gum_style(text, getattr(self.theme, "error", ""))
        return self

    def separator(self, char: str = "─", width: int = 50) -> "Popup":
        """Add separator line."""
        line = char * width
        self._add_gum_style(line, getattr(self.theme, "faint", ""))
        return self

    def choose(
        self,
        options: Union[List[str], List[Tuple[str, str]]],
        header: Optional[str] = None,
        height: int = 10,
        limit: int = 1,
        cursor: str = "→ ",
        selected_prefix: str = "✓ ",
        unselected_prefix: str = "○ ",
    ) -> Union[str, List[str]]:
        """Show choice selection in tmux popup.

        Args:
            options: List of strings or (value, display) tuples
            header: Header text for the choice list
            height: Maximum height of the list
            limit: Maximum number of selections (1 for single, >1 for multi)
            cursor: Cursor character
            selected_prefix: Prefix for selected items in multi-select
            unselected_prefix: Prefix for unselected items in multi-select

        Returns:
            Selected value(s) - when tuples are used, returns values not displays
        """
        result_file = tempfile.NamedTemporaryFile(mode="w+", suffix=".result", delete=False)
        self._cleanup_files.append(Path(result_file.name))

        has_tuples = any(isinstance(opt, tuple) for opt in options)

        cmd_parts = ["gum", "choose"]
        cmd_parts.extend(
            [
                "--height",
                str(height),
                "--cursor",
                shlex.quote(cursor),
                "--limit",
                str(limit),
                "--selected-prefix",
                shlex.quote(selected_prefix),
                "--unselected-prefix",
                shlex.quote(unselected_prefix),
            ]
        )

        if header:
            cmd_parts.extend(["--header", shlex.quote(header)])

        if has_tuples:
            cmd_parts.extend(["--label-delimiter", ":"])

            options_file = tempfile.NamedTemporaryFile(mode="w", suffix=".opts", delete=False)
            for option in options:
                if isinstance(option, tuple):
                    value, display = option
                    options_file.write(f"{display}:{value}\n")
                else:
                    options_file.write(f"{option}:{option}\n")
            options_file.close()
            self._cleanup_files.append(Path(options_file.name))

            self._add_line(f"{' '.join(cmd_parts)} < {options_file.name} > {result_file.name}")
        else:
            for option in options:
                assert isinstance(option, str)
                cmd_parts.append(shlex.quote(option))
            self._add_line(f"{' '.join(cmd_parts)} > {result_file.name}")

        self._show_popup()

        result_file.close()
        with open(result_file.name, "r") as f:
            result = f.read().strip()

        if limit == 1:
            return result
        else:
            return result.split("\n") if result else []

    def confirm(
        self, prompt: str = "Continue?", default: bool = False, yes_text: str = "Yes", no_text: str = "No"
    ) -> bool:
        """Show confirmation prompt in tmux popup."""

        result_file = tempfile.NamedTemporaryFile(mode="w+", suffix=".result", delete=False)
        self._cleanup_files.append(Path(result_file.name))

        cmd_parts = ["gum", "confirm", shlex.quote(prompt)]
        cmd_parts.extend(["--affirmative", shlex.quote(yes_text), "--negative", shlex.quote(no_text)])

        if default:
            cmd_parts.append("--default")

        self._add_line(f"if {' '.join(cmd_parts)}; then")
        self._add_line(f"  echo 'true' > {result_file.name}")
        self._add_line("else")
        self._add_line(f"  echo 'false' > {result_file.name}")
        self._add_line("fi")

        self._show_popup()

        result_file.close()
        with open(result_file.name, "r") as f:
            result = f.read().strip()

        return result == "true"

    def input(
        self,
        placeholder: str = "Type something...",
        header: Optional[str] = None,
        value: str = "",
        width: int = 0,
        char_limit: int = 400,
        password: bool = False,
    ) -> str:
        """Show input prompt in tmux popup."""

        result_file = tempfile.NamedTemporaryFile(mode="w+", suffix=".result", delete=False)
        self._cleanup_files.append(Path(result_file.name))

        cmd_parts = ["gum", "input"]
        cmd_parts.extend(
            ["--placeholder", shlex.quote(placeholder), "--value", shlex.quote(value), "--char-limit", str(char_limit)]
        )

        if header:
            cmd_parts.extend(["--header", shlex.quote(header)])
        if width:
            cmd_parts.extend(["--width", str(width)])
        if password:
            cmd_parts.append("--password")

        self._add_line(f"{' '.join(cmd_parts)} > {result_file.name}")

        self._show_popup()

        result_file.close()
        with open(result_file.name, "r") as f:
            result = f.read().strip()

        return result

    def pager(self, content: str, show_line_numbers: bool = False, soft_wrap: bool = True) -> None:
        """Show content in pager within tmux popup."""

        content_file = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
        content_file.write(content)
        content_file.close()
        self._cleanup_files.append(Path(content_file.name))

        cmd_parts = ["gum", "pager"]

        if show_line_numbers:
            cmd_parts.append("--show-line-numbers")
        if not soft_wrap:
            cmd_parts.append("--no-soft-wrap")

        cmd_parts.append(f"< {content_file.name}")

        self._add_line(" ".join(cmd_parts))

        self._show_popup()

    def filter(
        self,
        options: Union[List[str], List[Tuple[str, str]]],
        placeholder: str = "Type to search...",
        header: Optional[str] = None,
        limit: int = 1,
        fuzzy: bool = True,
        height: int = 0,
    ) -> Union[str, List[str]]:
        """Show fuzzy-searchable filter selection in tmux popup.

        Args:
            options: List of strings or (value, display) tuples.
            placeholder: Search box placeholder text. Defaults to "Type to search...".
            header: Optional header text above results.
            limit: Max selections (1 for single, 0 for unlimited). Defaults to 1.
            fuzzy: Enable fuzzy matching. Defaults to True.
            height: Display height (0 for auto). Defaults to 0.

        Returns:
            Selected value(s) - single string if limit=1, list otherwise.
        """
        result_file = tempfile.NamedTemporaryFile(mode="w+", suffix=".result", delete=False)
        self._cleanup_files.append(Path(result_file.name))

        has_tuples = any(isinstance(opt, tuple) for opt in options)

        # Create options file for filter input
        options_file = tempfile.NamedTemporaryFile(mode="w", suffix=".opts", delete=False)
        value_map = {}

        if has_tuples:
            for option in options:
                if isinstance(option, tuple):
                    value, display = option
                    options_file.write(f"{display}\n")
                    value_map[display] = value
                else:
                    options_file.write(f"{option}\n")
                    value_map[option] = option
        else:
            for option in options:
                assert isinstance(option, str)
                options_file.write(f"{option}\n")
        options_file.close()
        self._cleanup_files.append(Path(options_file.name))

        cmd_parts = ["gum", "filter"]

        if fuzzy:
            cmd_parts.append("--fuzzy")

        if limit == 0:
            cmd_parts.append("--no-limit")
        elif limit > 1:
            cmd_parts.extend(["--limit", str(limit)])

        cmd_parts.extend(["--placeholder", shlex.quote(placeholder)])

        if header:
            cmd_parts.extend(["--header", shlex.quote(header)])

        if height > 0:
            cmd_parts.extend(["--height", str(height)])

        self._add_line(f"{' '.join(cmd_parts)} < {options_file.name} > {result_file.name}")

        self._show_popup()

        result_file.close()
        with open(result_file.name, "r") as f:
            result_text = f.read().strip()

        if not result_text:
            return "" if limit == 1 else []

        if limit == 1:
            if has_tuples:
                return value_map.get(result_text, result_text)
            return result_text
        else:
            lines = result_text.split("\n")
            if has_tuples:
                return [value_map.get(line, line) for line in lines if line]
            return [line for line in lines if line]

    def table(
        self,
        rows: List[List[str]],
        headers: Optional[List[str]] = None,
        return_column: Optional[int] = None,
        separator: str = ",",
        border: str = "rounded",
        height: int = 0,
    ) -> str:
        """Show table selection in tmux popup.

        Args:
            rows: List of rows, each row is a list of column values
            headers: Optional column headers
            return_column: Column index to return (1-indexed, None returns full row)
            separator: Column separator for CSV format
            border: Border style (rounded, normal, thick, double, hidden)
            height: Table height (0 for auto)

        Returns:
            Selected value - either full row or specific column
        """

        result_file = tempfile.NamedTemporaryFile(mode="w+", suffix=".result", delete=False)
        self._cleanup_files.append(Path(result_file.name))

        data_file = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False)
        for row in rows:
            # Prevent CSV injection
            escaped_row = [str(col).replace(separator, f"\\{separator}") for col in row]
            data_file.write(separator.join(escaped_row) + "\n")
        data_file.close()
        self._cleanup_files.append(Path(data_file.name))

        cmd_parts = ["gum", "table"]
        cmd_parts.extend(
            [
                "--separator",
                shlex.quote(separator),
                "--border",
                border,
            ]
        )

        if headers:
            cmd_parts.extend(["--columns", shlex.quote(",".join(headers))])

        if return_column is not None:
            cmd_parts.extend(["--return-column", str(return_column)])

        if height > 0:
            cmd_parts.extend(["--height", str(height)])

        self._add_line(f"{' '.join(cmd_parts)} < {data_file.name} > {result_file.name}")

        self._show_popup()

        result_file.close()
        with open(result_file.name, "r") as f:
            result = f.read().strip()

        return result

    def show(self) -> None:
        """Display the popup with accumulated content."""
        self._show_popup()

    def _show_popup(self) -> None:
        """Execute the popup script in tmux display-popup."""
        if not self._script_lines:
            return

        script_file = tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False)
        script_file.write("#!/bin/bash\n")
        script_file.write("\n".join(self._script_lines))
        script_file.close()
        self._cleanup_files.append(Path(script_file.name))

        os.chmod(script_file.name, 0o755)

        popup_cmd = ["tmux", "display-popup"]

        if self.width:
            popup_cmd.extend(["-w", self.width])
        if self.height:
            popup_cmd.extend(["-h", self.height])

        if self.title:
            popup_cmd.extend(["-T", self.title])

        popup_cmd.extend(
            [
                "-E",
                script_file.name,
            ]
        )

        subprocess.run(popup_cmd, check=False)

        self._script_lines.clear()

    def cleanup(self) -> None:
        """Clean up temporary files."""
        for temp_file in self._cleanup_files:
            if temp_file.exists():
                temp_file.unlink()
        self._cleanup_files.clear()

    def __enter__(self) -> "Popup":
        """Context manager entry."""
        return self

    def __exit__(self, *args) -> None:
        """Context manager exit with cleanup."""
        self.cleanup()


def quick_confirm(message: str, default: bool = False) -> bool:
    """Quick confirmation dialog in tmux popup.

    Args:
        message: Confirmation message to display.
        default: Default choice if user presses Enter. Defaults to False.

    Returns:
        True if user confirmed, False otherwise.
    """
    with Popup() as p:
        p.header("Confirmation")
        p.text(message)
        return p.confirm("Proceed?", default=default)


def quick_choice(title: str, options: List[str]) -> Union[str, List[str]]:
    """Quick choice dialog in tmux popup.

    Args:
        title: Dialog title to display.
        options: List of choice options.

    Returns:
        Selected option string.
    """
    with Popup() as p:
        p.header(title)
        return p.choose(options)


def quick_input(prompt: str, password: bool = False) -> str:
    """Quick input dialog in tmux popup.

    Args:
        prompt: Input prompt message.
        password: Whether to mask input for passwords. Defaults to False.

    Returns:
        User input string.
    """
    with Popup() as p:
        p.header("Input Required")
        return p.input(placeholder=prompt, password=password)


def quick_info(title: str, message: str) -> None:
    """Quick info message in tmux popup.

    Args:
        title: Information dialog title.
        message: Information message to display.
    """
    with Popup() as p:
        p.header(title)
        p.info(message)
        p.text("\nPress Enter to close")
        p._add_line("read -r")
        p.show()
