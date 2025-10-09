"""CDP event data inspection and analysis commands."""

import json

from webtap.app import app
from webtap.commands._utils import evaluate_expression, format_expression_result
from webtap.commands._builders import check_connection, error_response
from webtap.commands._tips import get_mcp_description


mcp_desc = get_mcp_description("inspect")


@app.command(display="markdown", fastmcp={"type": "tool", "description": mcp_desc} if mcp_desc else {"type": "tool"})
def inspect(state, event: int = None, expr: str = None) -> dict:  # pyright: ignore[reportArgumentType]
    """Inspect CDP event or evaluate expression.

    Args:
        event: Event row ID to inspect (optional)
        expr: Python expression to evaluate (optional)

    Returns:
        Evaluation result or full CDP event
    """
    if event is None and expr is None:
        return error_response("Must provide at least one of: event (int) or expr (str)")

    if error := check_connection(state):
        return error

    # Handle pure expression evaluation (no event)
    if expr and event is None:
        try:
            # Create namespace with cdp and state
            namespace = {"cdp": state.cdp, "state": state}

            # Execute and get result + output
            result, output = evaluate_expression(expr, namespace)
            formatted_result = format_expression_result(result, output)

            # Build markdown response
            return {
                "elements": [
                    {"type": "heading", "content": "Expression Evaluation", "level": 2},
                    {"type": "text", "content": "**Expression:**"},
                    {"type": "code_block", "content": expr, "language": "python"},
                    {"type": "text", "content": "**Result:**"},
                    {"type": "code_block", "content": formatted_result, "language": ""},
                ]
            }
        except Exception as e:
            return error_response(
                f"{type(e).__name__}: {e}", suggestions=["cdp and state objects are available in namespace"]
            )

    # Handle event inspection (with optional expression)
    # Fetch event directly from DuckDB
    result = state.cdp.query("SELECT event FROM events WHERE rowid = ?", [event])

    if not result:
        return error_response(f"Event with rowid {event} not found")

    # Parse the CDP event
    data = json.loads(result[0][0])

    # No expression: show the raw data
    if not expr:
        # Pretty print the full CDP event as JSON
        elements = [{"type": "heading", "content": f"Event {event}", "level": 2}]

        # Add event method if available
        if isinstance(data, dict) and "method" in data:
            elements.append({"type": "text", "content": f"**Method:** `{data['method']}`"})

        # Add the full data as JSON code block
        # DATA-LEVEL TRUNCATION for memory/performance (similar to body.py)
        MAX_EVENT_SIZE = 2000
        if isinstance(data, dict):
            formatted = json.dumps(data, indent=2)
            if len(formatted) > MAX_EVENT_SIZE:
                elements.append({"type": "code_block", "content": formatted[:MAX_EVENT_SIZE], "language": "json"})
                elements.append(
                    {"type": "text", "content": f"_[truncated at {MAX_EVENT_SIZE} chars, {len(formatted)} total]_"}
                )
            else:
                elements.append({"type": "code_block", "content": formatted, "language": "json"})
        else:
            elements.append({"type": "code_block", "content": str(data), "language": ""})

        return {"elements": elements}

    # Execute code with data available (Jupyter-style)
    try:
        # Create namespace with data
        namespace = {"data": data}

        # Execute and get result + output
        result, output = evaluate_expression(expr, namespace)
        formatted_result = format_expression_result(result, output)

        # Build markdown response
        elements = [{"type": "heading", "content": f"Inspect Event {event}", "level": 2}]

        # Add event method if available
        if isinstance(data, dict) and "method" in data:
            elements.append({"type": "text", "content": f"**Method:** `{data['method']}`"})

        elements.extend(
            [
                {"type": "text", "content": "**Expression:**"},
                {"type": "code_block", "content": expr, "language": "python"},
                {"type": "text", "content": "**Result:**"},
                {"type": "code_block", "content": formatted_result, "language": ""},
            ]
        )

        return {"elements": elements}

    except Exception as e:
        # Provide helpful suggestions based on the error type
        suggestions = ["The event data is available as 'data' dict"]

        if "NameError" in str(type(e).__name__):
            suggestions.extend(
                [
                    "Common libraries are pre-imported: re, json, bs4, jwt, base64",
                    "Example: re.findall(r'pattern', str(data))",
                ]
            )
        elif "KeyError" in str(e):
            suggestions.extend(
                [
                    "Key not found. Try: list(data.keys()) to see available keys",
                    "CDP events are nested. Try: data.get('params', {}).get('response', {})",
                ]
            )
        elif "TypeError" in str(e):
            suggestions.extend(
                [
                    "Check data type: type(data)",
                    "For nested access, use: data.get('params', {}).get('field')",
                ]
            )

        return error_response(f"{type(e).__name__}: {e}", suggestions=suggestions)
