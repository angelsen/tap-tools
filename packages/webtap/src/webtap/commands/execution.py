"""JavaScript execution commands."""

from typing import Any

from webtap.app import app


@app.command()
def eval(state, expression: str, await_promise: bool = False) -> Any:
    """Evaluate JavaScript expression and return result.

    Args:
        expression: JavaScript expression to evaluate
        await_promise: Wait for promise resolution

    Returns:
        The evaluated result value

    Examples:
        >>> eval("document.title")
        'Example Page'

        >>> eval("[1, 2, 3].map(x => x * 2)")
        [2, 4, 6]

        >>> eval("fetch('/api/data').then(r => r.json())", await_promise=True)
        {'data': 'example'}
    """
    if not state.cdp.connected.is_set():
        raise RuntimeError("Not connected")

    result = state.cdp.execute(
        "Runtime.evaluate", {"expression": expression, "returnByValue": True, "awaitPromise": await_promise}
    )

    # Check for exceptions
    if result.get("exceptionDetails"):
        exception = result["exceptionDetails"]
        error_text = exception.get("exception", {}).get("description", str(exception))
        raise RuntimeError(f"JavaScript error: {error_text}")

    # Return the value
    return result.get("result", {}).get("value")


@app.command()
def exec(state, expression: str) -> dict:
    """Execute JavaScript without returning result.

    Useful for side effects like console.log or DOM manipulation.

    Args:
        expression: JavaScript code to execute

    Returns:
        Execution status

    Examples:
        >>> exec("console.log('Hello')")
        {'executed': True}

        >>> exec("document.body.style.background = 'red'")
        {'executed': True}
    """
    if not state.cdp.connected.is_set():
        raise RuntimeError("Not connected")

    result = state.cdp.execute(
        "Runtime.evaluate",
        {
            "expression": expression,
            "returnByValue": False,  # Don't need the result
        },
    )

    # Check for exceptions
    if result.get("exceptionDetails"):
        exception = result["exceptionDetails"]
        error_text = exception.get("exception", {}).get("description", str(exception))
        return {"executed": False, "error": error_text}

    return {"executed": True}
