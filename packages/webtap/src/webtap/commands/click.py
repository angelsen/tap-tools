"""Click element via CDP Input domain.

Commands: click
"""

from webtap.app import app
from webtap.commands._builders import success_response, rpc_call


@app.command(
    display="markdown",
    typer={"enabled": False},
    fastmcp={"type": "tool", "mime_type": "text/markdown"},
)
def click(
    state,
    selector: str,
    target: str,
    selection: int = None,  # pyright: ignore[reportArgumentType]
) -> dict:
    """Click a DOM element by CSS selector via CDP Input domain.

    Resolves the element to viewport coordinates and dispatches native mouse events.

    Args:
        selector: CSS selector for the element to click
        target: Target ID (e.g., "9222:abc123")
        selection: Browser selection number (overrides selector). Defaults to None.

    Examples:
        click("#submit-btn", "9222:abc")
        click("input[type=search]", "9222:abc")
        click("", "9222:abc", selection=1)
    """
    params: dict = {"selector": selector, "target": target}
    if selection is not None:
        params["selection"] = selection
    result, error = rpc_call(state, "click", **params)
    if error:
        return error
    return success_response(
        "Clicked element",
        details={
            "Selector": result.get("selector", selector),
            "Coordinates": f"({result.get('x', 0):.0f}, {result.get('y', 0):.0f})",
        },
    )


__all__ = ["click"]
