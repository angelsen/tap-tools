"""JavaScript code execution in browser context.

PUBLIC API:
  - js: Execute JavaScript code in the browser with optional promise handling
"""

from webtap.app import app
from webtap.commands._errors import check_connection, error_response
from webtap.commands._utils import build_info_response
from replkit2.textkit import markdown


@app.command(display="markdown")
def js(state, expression: str, wait_return: bool = True, await_promise: bool = False) -> dict:
    """Execute JavaScript in the browser.

    Args:
        expression: JavaScript code to execute
        wait_return: Wait for and return result (default: True)
        await_promise: Wait for promise resolution (default: False)

    Examples:
        js("document.title")                           # Get page title
        js("document.body.innerText.length")           # Get text length
        js("console.log('test')", wait_return=False)   # Fire and forget
        js("[...document.links].map(a => a.href)")    # Get all links

        # Async operations
        js("fetch('/api').then(r => r.json())", await_promise=True)

        # DOM manipulation (no return needed)
        js("document.querySelectorAll('.ad').forEach(e => e.remove())", wait_return=False)

        # Install interceptors
        js("window.fetch = new Proxy(window.fetch, {get: (t, p) => console.log(p)})", wait_return=False)

    Returns:
        The evaluated result if wait_return=True, otherwise execution status
    """
    if error := check_connection(state):
        return error

    result = state.cdp.execute(
        "Runtime.evaluate", {"expression": expression, "returnByValue": wait_return, "awaitPromise": await_promise}
    )

    # Check for exceptions
    if result.get("exceptionDetails"):
        exception = result["exceptionDetails"]
        error_text = exception.get("exception", {}).get("description", str(exception))

        return error_response("custom", custom_message=f"JavaScript error: {error_text}")

    # Return based on wait_return flag
    if wait_return:
        value = result.get("result", {}).get("value")

        # Format the result in markdown
        builder = markdown().heading("JavaScript Result", level=2)

        # Add the expression as a code block
        builder.code_block(expression, language="javascript")

        # Add the result
        if value is not None:
            if isinstance(value, (dict, list)):
                import json

                builder.code_block(json.dumps(value, indent=2), language="json")
            else:
                builder.text(f"**Result:** `{value}`")
        else:
            builder.text("**Result:** _(no return value)_")

        return builder.build()
    else:
        return build_info_response(
            title="JavaScript Execution",
            fields={
                "Status": "Executed",
                "Expression": expression[:50] + "..." if len(expression) > 50 else expression,
            },
        )
