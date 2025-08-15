"""Fuzzy search and filter a list.

PUBLIC API:
  - Filter: Interactive fuzzy finder for filtering and selecting items from lists
"""

from dataclasses import dataclass, field
from typing import Union, List, Dict, Any, cast
from ..core.base import Interactive


@dataclass
class Filter(Interactive):
    """Filter items from a list with fuzzy search.

    Filter provides an interactive fuzzy finder for selecting items.
    Unlike choose, filter shows a text input for filtering the options.
    """

    _gum_command = "filter"
    _needs_tty = True
    _capture_output = True

    # Core data that affects Python I/O
    options: Union[List[str], Dict[str, str]] = field(default_factory=list)

    def __init__(self, options: Union[List[str], Dict[str, str], None] = None, **gum_args: Any):
        """Initialize Filter with options and passthrough args.

        Args:
            options: List of strings or dict of label->value pairs
            **gum_args: All gum flags

        Common gum_args:
            limit: Maximum number of options to pick (default 1)
            no_limit: Pick unlimited options
            fuzzy: Enable fuzzy matching (default True)
            fuzzy_sort: Sort fuzzy results by score
            value: Initial filter value
            placeholder: Placeholder text (default "Filter...")
            prompt: Prompt to display (default "> ")
            header: Header text
            height: Input height
            width: Input width
            reverse: Display from bottom of screen
            strict: Only return if anything matched
            select_if_one: Auto-select if only one match
            output_delimiter: Delimiter for multiple results (default "\\n")
        """
        self.options = options or []
        self.gum_args = gum_args
        # Initialize base class storage
        self._parse_hints = {}

    def _prepare_data(self) -> tuple[list[str], dict[str, Any]]:
        """Convert Python data to gum format.

        Note: gum filter doesn't support label-delimiter like choose does,
        so we format dict entries as "label: value" for display.
        """
        args: list[str] = []

        # Determine if we're in dict mode
        is_dict = isinstance(self.options, dict)

        if is_dict:
            # Type narrowing - we know options is a dict here
            dict_options = cast(Dict[str, str], self.options)

            # Dict mode: format as "label: value" for display
            # We'll parse it back later
            formatted_options = [f"{label}: {value}" for label, value in dict_options.items()]
            args.extend(formatted_options)

            self._parse_hints = {"is_dict": True, "value_map": dict_options, "multiple": self._is_multiple()}
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
            # User cancelled or no matches
            return [] if hints["multiple"] else None

        # Parse based on output delimiter
        output_delimiter = self.gum_args.get("output_delimiter", "\n")
        lines = raw.strip().split(output_delimiter)

        if hints["is_dict"]:
            # Extract values from "label: value" format
            results = []
            value_map = hints["value_map"]

            for line in lines:
                # Try to parse as "label: value"
                if ": " in line:
                    label = line.split(": ", 1)[0]
                    # Look up the original value
                    if label in value_map:
                        results.append(value_map[label])
                    else:
                        # Fallback if label not found
                        results.append(line)
                else:
                    # No delimiter found, return as-is
                    results.append(line)
        else:
            # List mode: return the filtered strings as-is
            results = lines

        # Return based on single vs multiple
        if hints["multiple"]:
            return results
        else:
            return results[0] if results else None
