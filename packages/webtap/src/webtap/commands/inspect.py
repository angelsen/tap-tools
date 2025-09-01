"""Data inspection command for CDP events by rowid."""

import json

from webtap.app import app
from webtap.commands._utils import evaluate_expression, format_expression_result
from webtap.commands._errors import check_connection, error_response
from replkit2.textkit import markdown


@app.command(display="markdown")
def inspect(state, event: int | None = None, expr: str | None = None) -> dict:
    """
    Inspect CDP event by rowid with Python expressions.

    Full Python access for debugging. The event data is available as 'data'.

    Args:
        event: Event rowid to inspect (e.g., 47)
        expr: Python expression to evaluate

    Examples:
        # After running events()
        inspect(event=47)                           # Show full data
        inspect(event=47, expr="list(data.keys())") # Show field names

        # Parse JSON from CDP event
        inspect(event=47, expr="data['params']['response']['headers']")

        # Extract with regex
        inspect(event=48, expr="import re; re.findall(r'session=(\\w+)', str(data))")

        # Access nested CDP data
        inspect(event=47, expr="data['params']['response']['status']")

        # Complex analysis
        inspect(event=47, expr="data['method'], data['params'].keys()")

    Returns:
        Evaluation result or full CDP event
    """
    if not event:
        return error_response("custom", custom_message="Usage: inspect(event=rowid), e.g., inspect(event=47)")

    if error := check_connection(state):
        return error

    # Fetch event directly from DuckDB
    result = state.cdp.query("SELECT event FROM events WHERE rowid = ?", [event])

    if not result:
        return error_response("no_data", custom_message=f"Event with rowid {event} not found")

    # Parse the CDP event
    data = json.loads(result[0][0])

    # No expression: show the raw data
    if not expr:
        # Pretty print the full CDP event as JSON
        builder = markdown().heading(f"Event {event}", level=2)

        # Add event method if available
        if isinstance(data, dict) and "method" in data:
            builder.text(f"**Method:** `{data['method']}`")

        # Add the full data as JSON code block
        if isinstance(data, dict):
            formatted = json.dumps(data, indent=2)
            if len(formatted) > 2000:
                builder.code_block(formatted[:2000], language="json")
                builder.text(f"_[truncated, {len(formatted)} chars total]_")
            else:
                builder.code_block(formatted, language="json")
        else:
            builder.code_block(str(data), language="")

        return builder.build()

    # Execute code with data available (Jupyter-style)
    try:
        # Create namespace with data
        namespace = {"data": data}

        # Execute and get result + output
        result, output = evaluate_expression(expr, namespace)
        formatted_result = format_expression_result(result, output)

        # Build markdown response
        builder = markdown().heading(f"Inspect Event {event}", level=2)

        # Add event method if available
        if isinstance(data, dict) and "method" in data:
            builder.text(f"**Method:** `{data['method']}`")

        builder.text("**Expression:**")
        builder.code_block(expr, language="python")
        builder.text("**Result:**")
        builder.code_block(formatted_result, language="")

        return builder.build()

    except Exception as e:
        return error_response(
            "custom", custom_message=f"{type(e).__name__}: {e}", note="The event data is available as 'data' dict"
        )
