"""JavaScript code execution in browser context.

Commands: js
"""

import json

from replkit2.types import ExecutionContext

from webtap.app import app
from webtap.commands._builders import error_response, code_result_response, success_response, rpc_call
from webtap.commands._code_generation import ensure_output_directory
from webtap.commands._tips import get_mcp_description

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
    target: str,
    output: str = None,  # pyright: ignore[reportArgumentType]
    selection: int = None,  # pyright: ignore[reportArgumentType]
    persist: bool = False,
    wait_return: bool = True,
    await_promise: bool = False,
    _ctx: ExecutionContext = None,  # pyright: ignore[reportArgumentType]
) -> dict:
    """Execute JavaScript in the browser. Uses fresh scope by default to avoid redeclaration errors.

    Args:
        code: JavaScript code to execute (single expression by default, multi-statement with persist=True)
        target: Target ID (e.g., "9222:abc123")
        output: Write result to file instead of displaying
        selection: Browser selection number to bind to 'element' variable. Defaults to None.
        persist: Keep variables in global scope. Defaults to False.
        wait_return: Wait for and return result. Defaults to True.
        await_promise: Await promise results. Defaults to False.

    Examples:
        js("document.title")                           # Get page title
        js("[...document.links].map(a => a.href)")    # Get all links
        js("var x = 1; x + 1", persist=True)          # Multi-statement needs persist=True
        js("element.offsetWidth", selection=1)        # With browser element
        js("fetch('/api')", await_promise=True)       # Async operation
        js("setEquipment.toString()", output="out/fn.js")  # Export to file
    """
    params = {
        "code": code,
        "target": target,
        "selection": selection,
        "persist": persist,
        "await_promise": await_promise,
        "return_value": wait_return or bool(output),
    }
    result, error = rpc_call(state, "js", **params)
    if error:
        return error

    value = result.get("value")

    # Export to file if output path provided
    if output:
        if value is None:
            return error_response("Expression returned null/undefined")
        content = value if isinstance(value, str) else json.dumps(value, indent=2, default=str)
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

    if wait_return:
        return code_result_response("JavaScript Result", code, "javascript", result=value)
    else:
        # Truncate code for display
        is_repl = _ctx and _ctx.is_repl()
        max_len = 50 if is_repl else 200
        display_code = code if len(code) <= max_len else code[:max_len] + "..."

        return {
            "elements": [
                {"type": "heading", "content": "JavaScript Execution", "level": 2},
                {"type": "text", "content": f"**Status:** Executed\n\n**Expression:** `{display_code}`"},
            ]
        }
