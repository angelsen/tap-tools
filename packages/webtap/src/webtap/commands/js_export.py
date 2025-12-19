"""Export JavaScript evaluation results to local files.

This module provides the js_export command for saving JS eval output.
"""

from webtap.app import app
from webtap.commands._builders import error_response, success_response
from webtap.commands._code_generation import ensure_output_directory


@app.command(display="markdown", fastmcp={"type": "tool"})
def js_export(
    state,
    code: str,
    output: str,
    selection: int = None,  # pyright: ignore[reportArgumentType]
    persist: bool = False,
    await_promise: bool = False,
) -> dict:
    """Export JavaScript evaluation result to a local file.

    Args:
        code: JavaScript expression to evaluate (result is written to file)
        output: Output file path
        selection: Browser selection number to bind to 'element' variable. Defaults to None.
        persist: Keep variables in global scope. Defaults to False.
        await_promise: Await promise results. Defaults to False.

    Returns:
        Success or error response with file details.

    Examples:
        js_export("setEquipment.toString()", "out/fn.js")
        js_export("JSON.stringify(x2netvars, null, 2)", "out/vars.json")
    """
    # Execute JS via RPC
    try:
        result = state.client.call(
            "js",
            code=code,
            selection=selection,
            persist=persist,
            await_promise=await_promise,
            return_value=True,
        )
    except Exception as e:
        return error_response(f"JavaScript execution failed: {e}")

    if not result.get("executed"):
        return error_response("JavaScript execution did not complete")

    value = result.get("value")
    if value is None:
        return error_response("Expression returned null/undefined")

    # Convert to string if needed
    content = value if isinstance(value, str) else str(value)

    # Write to file
    output_path = ensure_output_directory(output)
    try:
        output_path.write_text(content)
    except Exception as e:
        return error_response(f"Failed to write file: {e}")

    return success_response(
        "Exported successfully",
        details={
            "Output": str(output_path),
            "Size": f"{output_path.stat().st_size} bytes",
            "Lines": len(content.splitlines()),
        },
    )
