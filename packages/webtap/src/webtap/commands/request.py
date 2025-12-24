"""Request details command with ES-style field selection.

Retrieve HAR request/response details with flexible field selection and Python expression evaluation.
"""

import json

from webtap.app import app
from webtap.client import RPCError
from webtap.commands._builders import error_response, success_response
from webtap.commands._code_generation import ensure_output_directory
from webtap.commands._tips import get_mcp_description
from webtap.commands._utils import evaluate_expression, format_expression_result

_mcp_desc = get_mcp_description("request")


@app.command(
    display="markdown",
    typer={"enabled": False},
    fastmcp={"type": "tool", "mime_type": "text/markdown", "description": _mcp_desc or ""},
)
def request(
    state,
    id: int,
    fields: list = None,  # pyright: ignore[reportArgumentType]
    expr: str = None,  # pyright: ignore[reportArgumentType]
    output: str = None,  # pyright: ignore[reportArgumentType]
) -> dict:
    """Get HAR request details with field selection and Python expressions.

    All commands have these pre-imported (no imports needed!):
    - **Web:** bs4/BeautifulSoup, lxml, ElementTree/ET
    - **Data:** json, yaml, msgpack, protobuf_json/protobuf_text
    - **Security:** jwt, base64, hashlib, cryptography
    - **HTTP:** httpx, urllib
    - **Text:** re, difflib, textwrap, html
    - **Utils:** datetime, collections, itertools, pprint, ast

    Examples:
      request(123)                           # Minimal (method, url, status)
      request(123, ["*"])                    # Everything
      request(123, ["request.headers.*"])    # Request headers
      request(123, ["response.content"])     # Fetch response body
      request(123, ["request.postData", "response.content"])  # Both bodies
      request(123, ["response.content"], expr="json.loads(data['response']['content']['text'])")  # Parse JSON
      request(123, ["*"], output="session.json")  # Export to file
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
            eval_result, stdout = evaluate_expression(expr, namespace)
            formatted = format_expression_result(eval_result, stdout)

            # Export to file if output path provided
            if output:
                output_path = ensure_output_directory(output)
                output_path.write_text(formatted)
                return success_response(
                    "Exported successfully",
                    details={
                        "Output": str(output_path),
                        "Size": f"{output_path.stat().st_size} bytes",
                        "Lines": len(formatted.splitlines()),
                    },
                )

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

    # Export to file if output path provided (no expr)
    if output:
        content = json.dumps(selected, indent=2, default=str)
        output_path = ensure_output_directory(output)
        output_path.write_text(content)
        return success_response(
            "Exported successfully",
            details={
                "Output": str(output_path),
                "Size": f"{output_path.stat().st_size} bytes",
                "Lines": len(content.splitlines()),
            },
        )

    # Build markdown response
    elements = [
        {"type": "heading", "content": f"Request {id}", "level": 2},
        {"type": "code_block", "content": json.dumps(selected, indent=2, default=str), "language": "json"},
    ]

    return {"elements": elements}


__all__ = ["request"]
