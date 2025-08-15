"""Select from a list of options.

PUBLIC API:
  - Choose: Interactive selection from a list with support for multiple selection and dict data
"""

from dataclasses import dataclass, field
from typing import Union, List, Dict, Any, cast
from ..core.base import Interactive


@dataclass
class Choose(Interactive):
    """Select one or more options from a list.

    Supports both simple list mode and dict mode (label:value pairs).
    All gum styling and behavior flags are passed through via gum_args.
    """

    _gum_command = "choose"
    _needs_tty = True
    _capture_output = True

    # Core data that affects Python I/O
    options: Union[List[str], Dict[str, str]] = field(default_factory=list)

    def __init__(self, options: Union[List[str], Dict[str, str], None] = None, **gum_args: Any):
        """Initialize Choose with options and passthrough args.

        Args:
            options: List of strings or dict of label->value pairs
            **gum_args: All gum flags (limit, no_limit, header, height, etc.)

        Common gum_args:
            limit: Maximum number of options to pick (default 1)
            no_limit: Pick unlimited options
            header: Header text to display
            height: Height of the list (default 10)
            selected: List of pre-selected options
            ordered: Maintain selection order
            select_if_one: Auto-select if only one option
            output_delimiter: Delimiter for multiple results (default "\\n")
            label_delimiter: For dict mode (e.g., ":")
        """
        self.options = options or []
        self.gum_args = gum_args
        # Initialize base class storage
        self._parse_hints = {}

    def _prepare_data(self) -> tuple[list[str], dict[str, Any]]:
        """Convert Python data to gum format."""
        args: list[str] = []

        # Determine if we're in dict mode
        is_dict = isinstance(self.options, dict)

        if is_dict:
            # Dict mode: format as label:value pairs
            # Use label_delimiter if provided, otherwise default to ":"
            delimiter = self.gum_args.get("label_delimiter", ":")

            # Type narrowing - we know options is a dict here
            dict_options = cast(Dict[str, str], self.options)

            # Format options as label:value
            formatted_options = [f"{label}{delimiter}{value}" for label, value in dict_options.items()]
            args.extend(formatted_options)

            # Tell gum about the delimiter
            if delimiter:
                args.extend(["--label-delimiter", delimiter])

            # Store parse hints
            self._parse_hints = {
                "is_dict": True,
                "value_map": dict_options,
                "delimiter": delimiter,
                "multiple": self._is_multiple(),
            }
        else:
            # List mode: pass strings directly
            args.extend(str(opt) for opt in self.options)

            self._parse_hints = {"is_dict": False, "multiple": self._is_multiple()}

        return args, self._parse_hints

    def _is_multiple(self) -> bool:
        """Check if multiple selection is enabled."""
        # Check for explicit no_limit
        if self.gum_args.get("no_limit"):
            return True
        # Check for limit > 1
        limit = self.gum_args.get("limit", 1)
        return limit != 1

    def _parse_result(self, raw: str, exit_code: int, hints: dict[str, Any]) -> Any:
        """Parse gum output back to Python data.

        Returns:
            - Single selection: str (or None if cancelled)
            - Multiple selection: List[str] (or [] if cancelled)
            - Dict mode: Returns values, not labels
        """
        if not raw.strip():
            # User cancelled or no selection
            return [] if hints["multiple"] else None

        # Parse based on output delimiter
        output_delimiter = self.gum_args.get("output_delimiter", "\n")
        lines = raw.strip().split(output_delimiter)

        if hints["is_dict"]:
            # In dict mode with label:value, gum returns the full "label:value"
            # We need to extract just the value part
            results = []
            delimiter = hints["delimiter"]
            value_map = hints["value_map"]

            for line in lines:
                if delimiter and delimiter in line:
                    # Split and get the label part to look up original value
                    label, _ = line.split(delimiter, 1)
                    # Return the original value from our map
                    if label in value_map:
                        results.append(value_map[label])
                    else:
                        # Fallback to the full line if label not found
                        results.append(line)
                else:
                    # No delimiter, return as-is
                    results.append(line)
        else:
            # List mode: return the selected strings as-is
            results = lines

        # Return based on single vs multiple
        if hints["multiple"]:
            return results
        else:
            return results[0] if results else None
