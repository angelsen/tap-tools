"""Selection commands for gum (choose, filter, file, table)."""

from typing import List, Optional, Tuple, Union
from .base import _SelectionCommand


class GumChoose(_SelectionCommand):
    """Choose from a list of options.

    Supports both simple strings and (value, display) tuples.
    """

    def __init__(
        self,
        options: Union[List[str], List[Tuple[str, str]]],
        limit: int = 1,
        height: int = 10,
        header: Optional[str] = None,
        cursor: str = "> ",
        selected_prefix: str = "✓ ",
        unselected_prefix: str = "○ ",
        timeout: Optional[int] = None,
        show_help: bool = True,
    ):
        """Initialize choose command.

        Args:
            options: List of strings or (value, display) tuples.
            limit: Max selections (1 for single, >1 for multi).
            height: Display height.
            header: Optional header text.
            cursor: Cursor indicator.
            selected_prefix: Prefix for selected items in multi-select.
            unselected_prefix: Prefix for unselected items in multi-select.
            timeout: Timeout in seconds.
            show_help: Whether to show help keybinds.
        """
        super().__init__("choose", limit, height, header, timeout, show_help)
        self.options = options
        self.cursor = cursor
        self.selected_prefix = selected_prefix
        self.unselected_prefix = unselected_prefix

        # Check if we have tuples
        self.has_tuples = any(isinstance(opt, tuple) for opt in options)
        self._value_map: dict = {}

    def render(self) -> List[str]:
        """Render choose command."""
        args = self.build_base_cmd()

        # Add selection args (height, limit, header, timeout)
        self.add_selection_args(args)

        # Choose-specific args
        args.extend(["--cursor", self.quote(self.cursor)])

        if self.limit > 1:
            args.extend(["--selected-prefix", self.quote(self.selected_prefix)])
            args.extend(["--unselected-prefix", self.quote(self.unselected_prefix)])

        # Handle options
        if self.has_tuples:
            # Create temp file with display values
            lines = []
            for option in self.options:
                if isinstance(option, tuple):
                    value, display = option
                    lines.append(display)
                    self._value_map[display] = value
                else:
                    lines.append(option)
                    self._value_map[option] = option

            # Use heredoc for options
            script = []
            if self._result_file:
                script.append(f"{' '.join(args)} << 'EOF' > {self._result_file}")
            else:
                script.append(f"{' '.join(args)} << 'EOF'")
            script.extend(lines)
            script.append("EOF")
            return script
        else:
            # Simple string options
            for option in self.options:
                args.append(self.quote(option))

            if self._result_file:
                return [f"{' '.join(args)} > {self._result_file}"]
            else:
                return [" ".join(args)]

    def parse_result(self, content: str) -> Union[str, List[str]]:
        """Parse choose result."""
        result = super().parse_result(content)

        # Map display values back to real values if using tuples
        if self.has_tuples:
            if isinstance(result, str):
                return self._value_map.get(result, result)
            else:
                return [self._value_map.get(r, r) for r in result]

        return result


class GumFilter(_SelectionCommand):
    """Filter items with fuzzy search."""

    def __init__(
        self,
        options: Union[List[str], List[Tuple[str, str]]],
        placeholder: str = "Type to search...",
        fuzzy: bool = True,
        limit: int = 1,
        height: int = 10,
        header: Optional[str] = None,
        timeout: Optional[int] = None,
        show_help: bool = True,
    ):
        """Initialize filter command.

        Args:
            options: List of strings or (value, display) tuples.
            placeholder: Search box placeholder.
            fuzzy: Enable fuzzy matching.
            limit: Max selections.
            height: Display height.
            header: Optional header text.
            timeout: Timeout in seconds.
            show_help: Whether to show help keybinds.
        """
        super().__init__("filter", limit, height, header, timeout, show_help)
        self.options = options
        self.placeholder = placeholder
        self.fuzzy = fuzzy

        # Check if we have tuples
        self.has_tuples = any(isinstance(opt, tuple) for opt in options)
        self._value_map: dict = {}

    def render(self) -> List[str]:
        """Render filter command."""
        args = self.build_base_cmd()

        # Add selection args
        self.add_selection_args(args)

        # Filter-specific args
        args.extend(["--placeholder", self.quote(self.placeholder)])

        if self.fuzzy:
            args.append("--fuzzy")

        # Handle options
        lines = []
        if self.has_tuples:
            for option in self.options:
                if isinstance(option, tuple):
                    value, display = option
                    lines.append(display)
                    self._value_map[display] = value
                else:
                    lines.append(option)
                    self._value_map[option] = option
        else:
            lines = list(self.options)

        # Use heredoc for options
        script = []
        if self._result_file:
            script.append(f"{' '.join(args)} << 'EOF' > {self._result_file}")
        else:
            script.append(f"{' '.join(args)} << 'EOF'")
        script.extend(lines)
        script.append("EOF")
        return script

    def parse_result(self, content: str) -> Union[str, List[str]]:
        """Parse filter result."""
        result = super().parse_result(content)

        # Map display values back to real values if using tuples
        if self.has_tuples:
            if isinstance(result, str):
                return self._value_map.get(result, result)
            else:
                return [self._value_map.get(r, r) for r in result]

        return result


class GumFile(_SelectionCommand):
    """File/directory picker."""

    def __init__(
        self,
        path: str = ".",
        file: bool = True,
        directory: bool = False,
        all: bool = False,
        height: int = 10,
        header: Optional[str] = None,
        timeout: Optional[int] = None,
        show_help: bool = True,
    ):
        """Initialize file picker.

        Args:
            path: Starting directory path.
            file: Allow file selection.
            directory: Allow directory selection.
            all: Show hidden files.
            height: Display height.
            header: Optional header text.
            timeout: Timeout in seconds.
            show_help: Whether to show help keybinds.
        """
        super().__init__("file", limit=1, height=height, header=header, timeout=timeout, show_help=show_help)
        self.path = path
        self.file = file
        self.directory = directory
        self.all = all

    def render(self) -> List[str]:
        """Render file command."""
        args = self.build_base_cmd()

        # Add starting path
        args.append(self.quote(self.path))

        # Add selection args
        self.add_selection_args(args)

        # File-specific args
        if self.file:
            args.append("--file")
        if self.directory:
            args.append("--directory")
        if self.all:
            args.append("--all")

        if self._result_file:
            return [f"{' '.join(args)} > {self._result_file}"]
        else:
            return [" ".join(args)]


class GumTable(_SelectionCommand):
    """Table selection with structured data."""

    def __init__(
        self,
        rows: List[List[str]],
        headers: Optional[List[str]] = None,
        separator: str = ",",
        return_column: Optional[int] = None,
        border: str = "rounded",
        height: int = 10,
        timeout: Optional[int] = None,
        show_help: bool = True,
    ):
        """Initialize table selection.

        Args:
            rows: List of rows, each row is a list of column values.
            headers: Optional column headers.
            separator: Column separator for CSV format.
            return_column: Column index to return (1-indexed, None for full row).
            border: Border style (rounded, normal, thick, double, hidden).
            height: Display height.
            timeout: Timeout in seconds.
            show_help: Whether to show help keybinds.
        """
        super().__init__("table", limit=1, height=height, header=None, timeout=timeout, show_help=show_help)
        self.rows = rows
        self.headers = headers
        self.separator = separator
        self.return_column = return_column
        self.border = border

    def render(self) -> List[str]:
        """Render table command."""
        args = self.build_base_cmd()

        # Table-specific args
        args.extend(["--separator", self.quote(self.separator)])
        args.extend(["--border", self.border])

        if self.headers:
            args.extend(["--columns", self.quote(",".join(self.headers))])

        if self.return_column is not None:
            args.extend(["--return-column", str(self.return_column)])

        if self.height > 0:
            args.extend(["--height", str(self.height)])

        self.add_timeout_arg(args)
        self.add_show_help_arg(args)

        # Create CSV data
        lines = []
        for row in self.rows:
            # Escape separator in values
            escaped_row = [str(col).replace(self.separator, f"\\{self.separator}") for col in row]
            lines.append(self.separator.join(escaped_row))

        # Use heredoc for data
        script = []
        if self._result_file:
            script.append(f"{' '.join(args)} << 'EOF' > {self._result_file}")
        else:
            script.append(f"{' '.join(args)} << 'EOF'")
        script.extend(lines)
        script.append("EOF")
        return script
