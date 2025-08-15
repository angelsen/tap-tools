"""Display or select from tabular data.

PUBLIC API:
  - Table: Interactive table display and selection with dict/list data support
"""

from dataclasses import dataclass, field
from typing import Union, List, Dict, Optional, Any
from ..core.base import Interactive


@dataclass
class Table(Interactive):
    """Display or interactively select from tabular data.

    Table can work in two modes:
    - Display mode (print=True): Just displays the table
    - Select mode (print=False): Interactive row selection

    Supports both list of lists and list of dicts as input.
    """

    _gum_command = "table"
    # Dynamic based on mode - set in __post_init__
    _needs_tty = False
    _capture_output = True

    # Core data
    data: Union[List[List[str]], List[Dict[str, str]]] = field(default_factory=list)
    headers: Optional[List[str]] = None

    def __init__(
        self,
        data: Union[List[List[str]], List[Dict[str, str]], None] = None,
        headers: Optional[List[str]] = None,
        **gum_args: Any,
    ):
        """Initialize Table with data and passthrough args.

        Args:
            data: List of rows (lists) or list of dicts
            headers: Column headers (auto-detected from dict keys if not provided)
            **gum_args: All gum flags

        Common gum_args:
            print: If True, display only (no interaction)
            separator: Column separator (default ",")
            widths: List of column widths
            height: Table height
            border: Border style (default "rounded")
            return_column: Column index to return (0 = whole row)
            timeout: Timeout in seconds
            file: Read data from file instead
        """
        self.data = data or []
        self.headers = headers
        self.gum_args = gum_args

        # Determine mode and set attributes accordingly
        is_print_mode = gum_args.get("print", False)
        self._needs_tty = not is_print_mode
        self._capture_output = not is_print_mode

        # Initialize base class storage
        self._parse_hints = {}

    def _prepare_data(self) -> tuple[list[str], dict[str, Any]]:
        """Convert table data to CSV format for gum.

        Gum table expects CSV data from stdin.
        """
        args: list[str] = []

        # Get separator from args
        separator = self.gum_args.get("separator", ",")

        # Determine if we have dict data
        is_dict_data = self.data and isinstance(self.data[0], dict)

        # Prepare rows
        rows: List[List[str]]
        if is_dict_data:
            # Type narrowing - we know data is List[Dict[str, str]] here
            dict_list: List[Dict[str, str]] = self.data  # type: ignore

            # Auto-detect headers from first dict if not provided
            if not self.headers and dict_list and isinstance(dict_list[0], dict):
                self.headers = list(dict_list[0].keys())

            # Convert each dict to a row based on headers
            rows = []
            if self.headers:
                for item in dict_list:
                    # Ensure item is treated as dict
                    if isinstance(item, dict):
                        row = [str(item.get(h, "")) for h in self.headers]
                        rows.append(row)
                    else:
                        # Shouldn't happen but handle gracefully
                        rows.append([str(item)])

            self._parse_hints = {
                "is_dict": True,
                "headers": self.headers,
                "separator": separator,
                "is_select": not self.gum_args.get("print", False),
                "return_column": self.gum_args.get("return_column", 0),
            }
        else:
            # List data - use as-is
            # Type narrowing - we know data is List[List[str]] here
            rows = self.data  # type: ignore

            self._parse_hints = {
                "is_dict": False,
                "headers": self.headers,
                "separator": separator,
                "is_select": not self.gum_args.get("print", False),
                "return_column": self.gum_args.get("return_column", 0),
            }

        # Convert rows to CSV format
        csv_lines = []
        for row in rows:
            # Ensure row is a list
            if isinstance(row, list):
                csv_line = separator.join(str(cell) for cell in row)
                csv_lines.append(csv_line)
            else:
                # Single value, treat as single-column row
                csv_lines.append(str(row))

        # Store CSV data for stdin
        self._parse_hints["stdin_data"] = "\n".join(csv_lines)

        # Add column headers if provided
        if self.headers:
            args.extend(["--columns", separator.join(self.headers)])

        # Add separator if not default
        if separator != ",":
            args.extend(["--separator", separator])

        return args, self._parse_hints

    def _parse_result(self, raw: str, exit_code: int, hints: dict[str, Any]) -> Any:
        """Parse table selection result.

        Returns:
            - Display mode: None
            - Select mode with return_column: The selected column value
            - Select mode without return_column: The full row (as list or dict)
        """
        # Display mode returns nothing
        if not hints.get("is_select", False):
            return None

        # No selection made
        if not raw.strip():
            return None

        # Check if returning specific column
        return_column = hints.get("return_column", 0)
        if return_column and return_column != 0:
            # Gum returns just the column value
            return raw.strip()

        # Parse full row selection
        separator = hints.get("separator", ",")
        values = raw.strip().split(separator)

        # Return as dict if original data was dict
        if hints.get("is_dict") and hints.get("headers"):
            return dict(zip(hints["headers"], values))

        # Return as list
        return values
