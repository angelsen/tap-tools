"""JavaScript code execution in browser context."""

from webtap.app import app
from webtap.commands._builders import check_connection, info_response, error_response, code_result_response
from webtap.commands._tips import get_mcp_description


mcp_desc = get_mcp_description("js")


@app.command(
    display="markdown",
    truncate={
        "Expression": {"max": 50, "mode": "end"}  # Only truncate for display in info response
    },
    fastmcp={"type": "tool", "description": mcp_desc} if mcp_desc else {"type": "tool"},
)
def js(
    state,
    code: str,
    selection: int = None,  # pyright: ignore[reportArgumentType]
    persist: bool = False,
    wait_return: bool = True,
    await_promise: bool = False,
) -> dict:
    """Execute JavaScript in the browser with optional element selection.

    Args:
        code: JavaScript code to execute (use 'element' variable if selection provided)
        selection: Browser element selection number (e.g., 1 for #1) - makes element available
        persist: Keep variables in global scope across calls (default: False, uses fresh scope)
        wait_return: Wait for and return result (default: True)
        await_promise: Await promises before returning (default: False)

    Examples:
        # Default: fresh scope (no redeclaration errors)
        js("const x = 1")                              # ✓ x isolated
        js("const x = 2")                              # ✓ No error, fresh scope
        js("document.title")                           # Get page title
        js("[...document.links].map(a => a.href)")    # Get all links

        # With browser element selection (always fresh scope)
        js("element.offsetWidth", selection=1)         # Use element #1
        js("element.classList", selection=2)           # Use element #2
        js("element.getBoundingClientRect()", selection=1)

        # Persistent scope: keep variables across calls
        js("var data = fetch('/api')", persist=True)   # data persists
        js("data.json()", persist=True)                # Access data from previous call

        # Async operations
        js("fetch('/api').then(r => r.json())", await_promise=True)

        # DOM manipulation (no return needed)
        js("document.querySelectorAll('.ad').forEach(e => e.remove())", wait_return=False)

    Returns:
        The evaluated result if wait_return=True, otherwise execution status
    """
    if error := check_connection(state):
        return error

    # Handle browser element selection
    if selection is not None:
        # Check if browser data exists
        if not hasattr(state, "browser_data") or not state.browser_data:
            return error_response(
                "No browser selections available",
                suggestions=[
                    "Use browser() to select elements first",
                    "Or omit the selection parameter to run code directly",
                ],
            )

        # Get the jsPath for the selected element
        selections = state.browser_data.get("selections", {})
        sel_key = str(selection)

        if sel_key not in selections:
            available = ", ".join(selections.keys()) if selections else "none"
            return error_response(
                f"Selection #{selection} not found",
                suggestions=[f"Available selections: {available}", "Use browser() to see all selections"],
            )

        js_path = selections[sel_key].get("jsPath")
        if not js_path:
            return error_response(f"Selection #{selection} has no jsPath")

        # Wrap code with element variable in fresh scope (IIFE)
        # Selection always uses fresh scope to avoid element redeclaration errors
        code = f"(() => {{ const element = {js_path}; return ({code}); }})()"
    elif not persist:
        # Default: wrap in IIFE for fresh scope (avoids const/let redeclaration errors)
        code = f"(() => {{ return ({code}); }})()"
    # else: persist=True, use code as-is (global scope)

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
        return code_result_response("JavaScript Result", code, "javascript", result=value)
    else:
        return info_response(
            title="JavaScript Execution",
            fields={
                "Status": "Executed",
                "Expression": code,  # Full expression, truncation in decorator
            },
        )
