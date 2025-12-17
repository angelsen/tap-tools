"""JavaScript code execution in browser context."""

from replkit2.types import ExecutionContext

from webtap.app import app
from webtap.commands._builders import info_response, error_response, code_result_response
from webtap.commands._tips import get_mcp_description

# Truncation values for Expression field in REPL mode
_REPL_EXPRESSION_MAX = 50

# Truncation values for Expression field in MCP mode
_MCP_EXPRESSION_MAX = 200


mcp_desc = get_mcp_description("js")


@app.command(
    display="markdown",
    fastmcp={"type": "tool", "mime_type": "text/markdown", "description": mcp_desc}
    if mcp_desc
    else {"type": "tool", "mime_type": "text/markdown"},
)
def js(
    state,
    code: str,
    selection: int = None,  # pyright: ignore[reportArgumentType]
    persist: bool = False,
    wait_return: bool = True,
    await_promise: bool = False,
    _ctx: ExecutionContext = None,  # pyright: ignore[reportArgumentType]
) -> dict:
    """Execute JavaScript in the browser. Uses fresh scope by default to avoid redeclaration errors.

    **Expression Mode (default):** Code is wrapped as `return (code)`, so use single expressions.
    Multi-statement code with semicolons will fail. Use `persist=True` for multi-statement code.

    Args:
        code: JavaScript code to execute (single expression by default, multi-statement with persist=True)
        selection: Browser element selection number - makes 'element' variable available
        persist: Keep variables in global scope across calls (default: False). Also enables multi-statement code.
        wait_return: Wait for and return result (default: True)
        await_promise: Await promises before returning (default: False)

    Examples:
        js("document.title")                           # Fresh scope (default)
        js("[...document.links].map(a => a.href)")    # Single expression works
        js("var x = 1; x + 1", persist=True)          # Multi-statement needs persist=True
        js("element.offsetWidth", selection=1)        # With browser element
        js("fetch('/api')", await_promise=True)       # Async operation
        js("element.remove()", selection=1, wait_return=False)  # No return needed

    Returns:
        Evaluated result if wait_return=True, otherwise execution status
    """
    # Check connection via daemon status
    try:
        status = state.client.status()
        if not status.get("connected"):
            return error_response("Not connected to any page. Use connect() first.")
    except Exception as e:
        return error_response(str(e))

    # Handle browser element selection
    if selection is not None:
        # Get selections from daemon status (already fetched above)
        browser = status.get("browser", {})
        selections = browser.get("selections", {})
        if not selections:
            return error_response(
                "No browser selections available",
                suggestions=[
                    "Use browser() to select elements first",
                    "Or omit the selection parameter to run code directly",
                ],
            )

        # Get the jsPath for the selected element
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

    # Execute via daemon client
    try:
        response = state.client.evaluate_js(code, await_promise=await_promise, return_by_value=wait_return)
    except Exception as e:
        return error_response(f"CDP error: {e}")

    # Extract result from daemon response
    result = response.get("result", {})

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
        # Mode-specific truncation for display
        is_repl = _ctx and _ctx.is_repl()
        max_len = _REPL_EXPRESSION_MAX if is_repl else _MCP_EXPRESSION_MAX
        display_code = code if len(code) <= max_len else code[:max_len] + "..."

        return info_response(
            title="JavaScript Execution",
            fields={
                "Status": "Executed",
                "Expression": display_code,
            },
        )
