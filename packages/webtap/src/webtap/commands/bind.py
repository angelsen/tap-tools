"""Page-callable bindings via Runtime.addBinding.

Commands: bind
"""

from webtap.app import app
from webtap.commands._builders import success_response, rpc_call


_bind_desc = """Register page-callable bindings that route to console.

When bound, page JS can call window.{name}(payload) and the call appears as a console
message with source='binding'. Payload MUST be a string (JSON.stringify if needed).

Bindings survive navigation but NOT target reconnection (watch/unwatch).

Examples:
  bind("myCallback", target="9222:abc")                    # Register binding
  js("window.myCallback('hello')", target="9222:abc")      # Page calls it
  console()                                                  # Shows [myCallback] hello
  bind("myCallback", target="9222:abc", remove=True)       # Remove binding
"""


@app.command(
    display="markdown",
    typer={"enabled": False},
    fastmcp={"type": "tool", "mime_type": "text/markdown", "description": _bind_desc},
)
def bind(
    state,
    name: str,
    target: str = None,  # pyright: ignore[reportArgumentType]
    remove: bool = False,
) -> dict:
    """Register or remove a page-callable binding.

    Args:
        name: Binding name (becomes window.{name} in page JS)
        target: Target ID (e.g., "9222:abc123")
        remove: Remove the binding. Defaults to False.

    Examples:
        bind("myCallback", target="9222:abc")              # Register
        bind("myCallback", target="9222:abc", remove=True) # Remove
    """
    if remove:
        result, error = rpc_call(state, "bind_remove", name=name, target=target)
        if error:
            return error
        return success_response(f"Removed binding '{name}'")

    result, error = rpc_call(state, "bind", name=name, target=target)
    if error:
        return error
    return success_response(
        f"Binding '{name}' registered",
        details={"Usage": f"window.{name}('payload') from page JS"},
    )


__all__ = ["bind"]
