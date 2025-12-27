"""Console entry details command with field selection.

Commands: entry
"""

import json

from webtap.app import app
from webtap.client import RPCError
from webtap.commands._builders import error_response, success_response
from webtap.commands._code_generation import ensure_output_directory
from webtap.commands._tips import get_mcp_description
from webtap.commands._utils import evaluate_expression, format_expression_result

_mcp_desc = get_mcp_description("entry")


@app.command(
    display="markdown",
    typer={"enabled": False},
    fastmcp={"type": "tool", "mime_type": "text/markdown", "description": _mcp_desc or ""},
)
def entry(
    state,
    id: int,
    fields: list = None,  # pyright: ignore[reportArgumentType]
    expr: str = None,  # pyright: ignore[reportArgumentType]
    output: str = None,  # pyright: ignore[reportArgumentType]
) -> dict:
    """Get console entry details with field selection and Python expressions.

    All commands have these pre-imported (no imports needed!):
    - **Web:** bs4/BeautifulSoup, lxml, ElementTree/ET
    - **Data:** json, yaml, msgpack, protobuf_json/protobuf_text
    - **Security:** jwt, base64, hashlib, cryptography
    - **HTTP:** httpx, urllib
    - **Text:** re, difflib, textwrap, html
    - **Utils:** datetime, collections, itertools, pprint, ast

    Examples:
      entry(5)                    # Minimal (level, message, source)
      entry(5, ["*"])             # Full CDP event
      entry(5, ["stackTrace"])    # Stack trace only
      entry(5, ["args.*"])        # All arguments
      entry(5, expr="len(data['args'])")  # Count arguments
      entry(5, ["*"], output="error.json")  # Export to file
    """
    # Get console entry from daemon via RPC
    # Field selection happens server-side
    try:
        result = state.client.call("entry", id=id, fields=fields)
        selected = result.get("entry")
    except RPCError as e:
        return error_response(e.message)
    except Exception as e:
        return error_response(str(e))

    if not selected:
        return error_response(f"Console entry {id} not found")

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
                    "Example: data['stackTrace']['callFrames'][0]",
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

    # Build markdown response with formatted stack trace if present
    elements = [{"type": "heading", "content": f"Console Entry {id}", "level": 2}]

    # Format stack trace if present
    if "stackTrace" in selected and selected.get("stackTrace"):
        stack_trace = selected["stackTrace"]
        frames = stack_trace.get("callFrames", [])
        if frames:
            formatted_frames = []
            for frame in frames:
                func_name = frame.get("functionName") or "(anonymous)"
                url = frame.get("url", "")
                line = frame.get("lineNumber", 0)
                col = frame.get("columnNumber", 0)
                formatted_frames.append(f"  at {func_name} ({url}:{line}:{col})")
            elements.append({"type": "heading", "content": "Stack Trace", "level": 3})
            elements.append({"type": "code_block", "content": "\n".join(formatted_frames), "language": ""})

    # Add full entry JSON
    elements.append({"type": "code_block", "content": json.dumps(selected, indent=2, default=str), "language": "json"})

    return {"elements": elements}


__all__ = ["entry"]
