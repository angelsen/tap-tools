"""Request details command with ES-style field selection."""

from webtap.app import app
from webtap.commands._builders import error_response
from webtap.commands._tips import get_mcp_description
from webtap.commands._utils import evaluate_expression, format_expression_result

_mcp_desc = get_mcp_description("request")

# Minimal fields for default view
MINIMAL_FIELDS = ["request.method", "request.url", "response.status", "time", "state"]


def _get_nested(obj: dict | None, path: list[str]):
    """Get nested value by path, case-insensitive for headers."""
    for key in path:
        if obj is None:
            return None
        if isinstance(obj, dict):
            # Case-insensitive lookup
            matching_key = next((k for k in obj.keys() if k.lower() == key.lower()), None)
            if matching_key:
                obj = obj.get(matching_key)
            else:
                return None
        else:
            return None
    return obj


def _set_nested(result: dict, path: list[str], value) -> None:
    """Set nested value by path, creating intermediate dicts."""
    current = result
    for key in path[:-1]:
        if key not in current:
            current[key] = {}
        current = current[key]
    current[path[-1]] = value


def _select_fields(har_entry: dict, patterns: list[str] | None, fetch_body_fn) -> dict:
    """Apply ES-style field selection to HAR entry.

    Args:
        har_entry: Full HAR entry with nested structure.
        patterns: Field patterns or None for minimal.
        fetch_body_fn: Function to fetch body on-demand.

    Patterns:
        - None: minimal default fields
        - ["*"]: all fields
        - ["request.*"]: all request fields
        - ["request.headers.*"]: all request headers
        - ["request.headers.content-type"]: specific header
        - ["response.content"]: fetch response body on-demand
    """
    if patterns is None:
        # Minimal default - extract specific paths
        result: dict = {}
        for pattern in MINIMAL_FIELDS:
            parts = pattern.split(".")
            value = _get_nested(har_entry, parts)
            if value is not None:
                _set_nested(result, parts, value)
        return result

    if patterns == ["*"]:
        return har_entry

    result = {}
    for pattern in patterns:
        if pattern == "*":
            return har_entry

        parts = pattern.split(".")

        # Special case: response.content triggers body fetch
        if pattern == "response.content" or pattern.startswith("response.content."):
            request_id = har_entry.get("request_id")
            if request_id:
                body_result = fetch_body_fn(request_id)
                if body_result:
                    content = har_entry.get("response", {}).get("content", {}).copy()
                    content["text"] = body_result.get("body")
                    content["encoding"] = "base64" if body_result.get("base64Encoded") else None
                    _set_nested(result, ["response", "content"], content)
                else:
                    _set_nested(result, ["response", "content"], {"text": None})
            continue

        # Wildcard: "request.headers.*" -> get all under that path
        if pattern.endswith(".*"):
            prefix = pattern[:-2]
            prefix_parts = prefix.split(".")
            obj = _get_nested(har_entry, prefix_parts)
            if obj is not None:
                _set_nested(result, prefix_parts, obj)
        else:
            # Specific path
            value = _get_nested(har_entry, parts)
            if value is not None:
                _set_nested(result, parts, value)

    return result


@app.command(
    display="markdown",
    fastmcp={"type": "tool", "mime_type": "text/markdown", "description": _mcp_desc or ""},
)
def request(
    state,
    id: int,
    fields: list = None,  # type: ignore[reportArgumentType]
    expr: str = None,  # type: ignore[reportArgumentType]
) -> dict:
    """Get HAR request details with field selection.

    Args:
        id: Row ID from network() output
        fields: ES-style field patterns (HAR structure)
            - None: minimal (method, url, status, time, state)
            - ["*"]: all fields
            - ["request.*"]: all request fields
            - ["request.headers.*"]: all request headers
            - ["request.postData"]: request body
            - ["response.headers.*"]: all response headers
            - ["response.content"]: fetch response body on-demand
        expr: Python expression with 'data' variable containing selected fields

    Examples:
        request(123)                           # Minimal
        request(123, ["*"])                    # Everything
        request(123, ["request.headers.*"])    # Request headers
        request(123, ["response.content"])     # Fetch response body
        request(123, ["request.postData", "response.content"])  # Both bodies
        request(123, ["response.content"], expr="json.loads(data['response']['content']['text'])")
    """
    # Check connection
    try:
        status = state.client.status()
        if not status.get("connected"):
            return error_response("Not connected. Use connect() first.")
    except Exception as e:
        return error_response(str(e))

    # Get HAR entry from daemon
    try:
        har_entry = state.client.request_details(id)
    except Exception as e:
        return error_response(str(e))

    if not har_entry:
        return error_response(f"Request {id} not found")

    # Apply field selection
    def fetch_body(request_id: str) -> dict | None:
        try:
            return state.client.fetch_body(request_id)
        except Exception:
            return None

    result = _select_fields(har_entry, fields, fetch_body)

    # If expr provided, evaluate it with data available
    if expr:
        try:
            namespace = {"data": result}
            eval_result, output = evaluate_expression(expr, namespace)
            formatted = format_expression_result(eval_result, output)

            return {
                "elements": [
                    {"type": "heading", "content": "Expression Result", "level": 2},
                    {"type": "code_block", "content": expr, "language": "python"},
                    {"type": "text", "content": "**Result:**"},
                    {"type": "code_block", "content": formatted, "language": ""},
                ]
            }
        except Exception as e:
            return error_response(
                f"{type(e).__name__}: {e}",
                suggestions=[
                    "The selected fields are available as 'data' variable",
                    "Common libraries are pre-imported: re, json, bs4, jwt, httpx",
                    "Example: json.loads(data['response']['content']['text'])",
                ],
            )

    # Build markdown response
    import json

    elements = [
        {"type": "heading", "content": f"Request {id}", "level": 2},
        {"type": "code_block", "content": json.dumps(result, indent=2, default=str), "language": "json"},
    ]

    return {"elements": elements}


__all__ = ["request"]
