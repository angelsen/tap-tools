"""Code generation utilities for transforming HTTP bodies into code.

Pure transformation functions with no dependencies on services or state.
Used by to_model(), quicktype(), and future code generation commands.
"""

import json
from pathlib import Path
from typing import Any


def parse_json(content: str) -> tuple[Any, str | None]:
    """Parse JSON string into Python object.

    Args:
        content: JSON string to parse.

    Returns:
        Tuple of (parsed_data, error_message).
        On success: (data, None)
        On failure: (None, error_string)

    Examples:
        data, error = parse_json('{"key": "value"}')
        if error:
            return error_response(error)
    """
    try:
        return json.loads(content), None
    except json.JSONDecodeError as e:
        return None, f"Invalid JSON: {e}"


def extract_json_path(data: Any, path: str) -> tuple[Any, str | None]:
    """Extract nested data using simple bracket notation.

    Supports paths like "data[0]", "results.users", or "data[0].items".

    Args:
        data: Dict or list to extract from.
        path: Path using dot and bracket notation.

    Returns:
        Tuple of (extracted_data, error_message).
        On success: (data, None)
        On failure: (None, error_string)

    Examples:
        result, err = extract_json_path({"data": [1,2,3]}, "data[0]")
        # result = 1, err = None

        result, err = extract_json_path({"user": {"name": "Bob"}}, "user.name")
        # result = "Bob", err = None
    """
    try:
        parts = path.replace("[", ".").replace("]", "").split(".")
        result = data
        for part in parts:
            if part:
                if part.isdigit():
                    result = result[int(part)]
                else:
                    result = result[part]
        return result, None
    except (KeyError, IndexError, TypeError) as e:
        return None, f"JSON path '{path}' not found: {e}"


def validate_generation_data(data: Any) -> tuple[bool, str | None]:
    """Validate data structure for code generation.

    Code generators (Pydantic, quicktype) require dict or list structures.

    Args:
        data: Data to validate.

    Returns:
        Tuple of (is_valid, error_message).
        On success: (True, None)
        On failure: (False, error_string)

    Examples:
        is_valid, error = validate_generation_data({"key": "value"})
        # is_valid = True, error = None

        is_valid, error = validate_generation_data("string")
        # is_valid = False, error = "Data is str, not dict or list"
    """
    if not isinstance(data, (dict, list)):
        return False, f"Data is {type(data).__name__}, not dict or list"
    return True, None


def ensure_output_directory(output: str) -> Path:
    """Create output directory if needed, return resolved path.

    Args:
        output: Output file path (can be relative, use ~, etc.).

    Returns:
        Resolved absolute Path object.

    Examples:
        path = ensure_output_directory("~/models/user.py")
        # Creates ~/models/ if it doesn't exist
        # Returns Path("/home/user/models/user.py")
    """
    output_path = Path(output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    return output_path
