"""JavaScript code execution in browser context."""

from replkit2.types import ExecutionContext

from webtap.app import app
from webtap.client import RPCError
from webtap.commands._builders import error_response, code_result_response
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
    selection: int = None,  # pyright: ignore[reportArgumentType]
    persist: bool = False,
    wait_return: bool = True,
    await_promise: bool = False,
    _ctx: ExecutionContext = None,  # pyright: ignore[reportArgumentType]
) -> dict:
    """Execute JavaScript in the browser. Uses fresh scope by default to avoid redeclaration errors.

    Args:
        code: JavaScript code to execute (single expression by default, multi-statement with persist=True)
        selection: Browser element selection number - makes 'element' variable available
        persist: Keep variables in global scope across calls (default: False)
        wait_return: Wait for and return result (default: True)
        await_promise: Await promises before returning (default: False)

    Examples:
        js("document.title")                           # Fresh scope (default)
        js("[...document.links].map(a => a.href)")    # Single expression works
        js("var x = 1; x + 1", persist=True)          # Multi-statement needs persist=True
        js("element.offsetWidth", selection=1)        # With browser element
        js("fetch('/api')", await_promise=True)       # Async operation
        js("element.remove()", selection=1, wait_return=False)  # No return needed
    """
    try:
        result = state.client.call(
            "js",
            code=code,
            selection=selection,
            persist=persist,
            await_promise=await_promise,
            return_value=wait_return,
        )

        if wait_return:
            return code_result_response("JavaScript Result", code, "javascript", result=result.get("value"))
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

    except RPCError as e:
        return error_response(e.message)
    except Exception as e:
        return error_response(str(e))
