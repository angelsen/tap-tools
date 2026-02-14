"""Code generation utilities for transforming HTTP bodies into code.

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


def prepare_generation_data(
    state,
    id: int,
    target: str,
    field: str = "response.content",
    json_path: str | None = None,
    expr: str | None = None,
) -> tuple[Any, Any, dict | None]:
    """Fetch and prepare data for code generation from a HAR entry.

    Shared pipeline for to_model() and quicktype():
    1. Fetch HAR entry via RPC
    2. Fetch body content
    3. Evaluate expression OR parse JSON
    4. Extract JSON path
    5. Validate structure

    Args:
        state: WebTap state with RPC client.
        id: Row ID from network() output.
        target: Target ID.
        field: Body field - "response.content" or "request.postData".
        json_path: Optional path to extract nested data.
        expr: Optional Python expression to transform data.

    Returns:
        Tuple of (data, har_entry, error_response).
        On success: (data, har_entry, None)
        On failure: (None, None, error_dict)
    """
    from webtap.commands._builders import error_response
    from webtap.commands._utils import evaluate_expression, fetch_body_content

    try:
        result = state.client.call("request", id=id, target=target, fields=["*"])
        har_entry = result.get("entry")
    except Exception as e:
        return None, None, error_response(f"Failed to get request: {e}")

    if not har_entry:
        return None, None, error_response(f"Request {id} not found")

    body_content, err = fetch_body_content(state, har_entry, field)
    if err or body_content is None:
        return (
            None,
            None,
            error_response(
                err or "Failed to fetch body",
                suggestions=[
                    f"Field '{field}' could not be fetched",
                    "For response body: field='response.content'",
                    "For POST data: field='request.postData'",
                ],
            ),
        )

    if expr:
        try:
            namespace = {"body": body_content}
            data, _ = evaluate_expression(expr, namespace)
        except Exception as e:
            return (
                None,
                None,
                error_response(
                    f"Expression failed: {e}",
                    suggestions=[
                        "Variable available: 'body' (str)",
                        "Example: json.loads(body)['data'][0]",
                        "Example: dict(urllib.parse.parse_qsl(body))",
                    ],
                ),
            )
    else:
        if not body_content.strip():
            return None, None, error_response("Body is empty")

        data, parse_err = parse_json(body_content)
        if parse_err:
            return (
                None,
                None,
                error_response(
                    parse_err,
                    suggestions=[
                        "Body must be valid JSON, or use expr to transform it",
                        'For form data: expr="dict(urllib.parse.parse_qsl(body))"',
                    ],
                ),
            )

    if json_path:
        data, err = extract_json_path(data, json_path)
        if err:
            return (
                None,
                None,
                error_response(
                    err,
                    suggestions=[
                        f"Path '{json_path}' not found in body",
                        'Try a simpler path like "data" or "data[0]"',
                    ],
                ),
            )

    is_valid, validation_err = validate_generation_data(data)
    if not is_valid:
        return (
            None,
            None,
            error_response(
                validation_err or "Invalid data structure",
                suggestions=[
                    "Code generation requires dict or list structure",
                    "Use json_path or expr to extract a complex object",
                ],
            ),
        )

    return data, har_entry, None
