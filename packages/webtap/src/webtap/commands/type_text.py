"""Type text into element via CDP Input domain.

Commands: type_text
"""

from webtap.app import app
from webtap.commands._builders import success_response, rpc_call


@app.command(
    display="markdown",
    typer={"enabled": False},
    fastmcp={"type": "tool", "mime_type": "text/markdown"},
)
def type_text(
    state,
    selector: str,
    text: str,
    target: str,
    delay_ms: int = 50,
    selection: int = None,  # pyright: ignore[reportArgumentType]
) -> dict:
    """Type text into a DOM element via CDP Input domain keystrokes.

    Clicks the element to focus it, then dispatches native key events for each character.
    Use {KeyName} for special keys: Enter, Tab, Escape, Backspace, Delete,
    ArrowUp, ArrowDown, ArrowLeft, ArrowRight, Home, End, PageUp, PageDown, Space.

    Args:
        selector: CSS selector for the input element
        text: Text to type. Use {Enter}, {Tab} etc. for special keys.
        target: Target ID (e.g., "9222:abc123")
        delay_ms: Delay between keystrokes in ms. Defaults to 50.
        selection: Browser selection number (overrides selector). Defaults to None.

    Examples:
        type_text("#search", "hello world{Enter}", "9222:abc")
        type_text("input[name=email]", "user@example.com{Tab}", "9222:abc")
        type_text("#input", "{Backspace}{Backspace}", "9222:abc")
        type_text("", "text", "9222:abc", selection=1)
    """
    params: dict = {"selector": selector, "text": text, "target": target, "delay_ms": delay_ms}
    if selection is not None:
        params["selection"] = selection
    result, error = rpc_call(state, "type", **params)
    if error:
        return error
    return success_response(
        "Text typed",
        details={
            "Selector": result.get("selector", selector),
            "Characters": str(len(text)),
            "Delay": f"{delay_ms}ms",
        },
    )


__all__ = ["type_text"]
