"""Request details command with ES-style field selection."""

import json

from webtap.app import app
from webtap.client import RPCError
from webtap.commands._builders import error_response
from webtap.commands._tips import get_mcp_description
from webtap.commands._utils import evaluate_expression, format_expression_result

_mcp_desc = get_mcp_description("request")


@app.command(
    display="markdown",
    fastmcp={"type": "tool", "mime_type": "text/markdown", "description": _mcp_desc or ""},
)
def request(
    state,
    id: int,
    fields: list = None,  # pyright: ignore[reportArgumentType]
    expr: str = None,  # pyright: ignore[reportArgumentType]
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
    # Get pre-selected HAR entry from daemon via RPC
    # Field selection (including body fetch) happens server-side
    try:
        result = state.client.call("request", id=id, fields=fields)
        selected = result.get("entry")
    except RPCError as e:
        return error_response(e.message)
    except Exception as e:
        return error_response(str(e))

    if not selected:
        return error_response(f"Request {id} not found")

    # If expr provided, evaluate it with data available
    if expr:
        try:
            namespace = {"data": selected}
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
    elements = [
        {"type": "heading", "content": f"Request {id}", "level": 2},
        {"type": "code_block", "content": json.dumps(selected, indent=2, default=str), "language": "json"},
    ]

    return {"elements": elements}


__all__ = ["request"]
