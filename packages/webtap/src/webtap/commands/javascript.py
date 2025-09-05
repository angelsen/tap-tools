"""JavaScript code execution in browser context."""

import json
from webtap.app import app
from webtap.commands._errors import check_connection
from webtap.commands._builders import info_response, error_response
from webtap.commands._tips import get_mcp_description


mcp_desc = get_mcp_description("js")


@app.command(
    display="markdown",
    truncate={
        "Expression": {"max": 50, "mode": "end"}  # Only truncate for display in info response
    },
    fastmcp={"type": "tool", "description": mcp_desc} if mcp_desc else {"type": "tool"},
)
def js(state, code: str, wait_return: bool = True, await_promise: bool = False) -> dict:
    """Execute JavaScript in the browser.

    Args:
        code: JavaScript code to execute
        wait_return: Wait for and return result (default: True)
        await_promise: Await promises before returning (default: False)

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
        "Runtime.evaluate", {"expression": code, "returnByValue": wait_return, "awaitPromise": await_promise}
    )

    # Check for exceptions
    if result.get("exceptionDetails"):
        exception = result["exceptionDetails"]
        error_text = exception.get("exception", {}).get("description", str(exception))

        return error_response(f"JavaScript error: {error_text}")

    # Return based on wait_return flag
    if wait_return:
        value = result.get("result", {}).get("value")

        # Format the result in markdown
        elements = [
            {"type": "heading", "content": "JavaScript Result", "level": 2},
            {"type": "code_block", "content": code, "language": "javascript"},  # Full code
        ]

        # Add the result
        if value is not None:
            if isinstance(value, (dict, list)):
                elements.append({"type": "code_block", "content": json.dumps(value, indent=2), "language": "json"})
            else:
                elements.append({"type": "text", "content": f"**Result:** `{value}`"})
        else:
            elements.append({"type": "text", "content": "**Result:** _(no return value)_"})

        return {"elements": elements}
    else:
        return info_response(
            title="JavaScript Execution",
            fields={
                "Status": "Executed",
                "Expression": code,  # Full expression, truncation in decorator
            },
        )
