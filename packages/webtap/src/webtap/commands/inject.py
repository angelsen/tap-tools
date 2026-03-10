"""Persistent script injection via Page.addScriptToEvaluateOnNewDocument.

Commands: inject
"""

from webtap.app import app
from webtap.commands._builders import error_response, info_response, success_response, table_response, rpc_call


_inject_desc = """Inject persistent scripts that survive page navigation.

Scripts run via Page.addScriptToEvaluateOnNewDocument - they execute on every new document
(navigation, reload) until removed. Scripts do NOT survive target reconnection (watch/unwatch).

Examples:
  inject("console.log('alive')", target="9222:abc")          # Add persistent script
  inject(target="9222:abc")                                    # List active injections
  inject(id="1", target="9222:abc", remove=True)              # Remove by identifier
"""


@app.command(
    display="markdown",
    typer={"enabled": False},
    fastmcp={"type": "tool", "mime_type": "text/markdown", "description": _inject_desc},
)
def inject(
    state,
    code: str = None,  # pyright: ignore[reportArgumentType]
    target: str = None,  # pyright: ignore[reportArgumentType]
    id: str = None,  # pyright: ignore[reportArgumentType]
    remove: bool = False,
) -> dict:
    """Inject persistent scripts that survive page navigation.

    Args:
        code: JavaScript code to inject persistently
        target: Target ID (e.g., "9222:abc123")
        id: Injection identifier (for removal)
        remove: Remove injection by id. Defaults to False.

    Examples:
        inject("console.log('alive')", target="9222:abc")  # Add script
        inject(target="9222:abc")                            # List active
        inject(id="1", target="9222:abc", remove=True)      # Remove
    """
    if remove:
        if not id:
            return error_response("id is required for removal")
        result, error = rpc_call(state, "inject_remove", id=id, target=target)
        if error:
            return error
        return success_response(f"Removed injection {id}")

    if code:
        result, error = rpc_call(state, "inject", code=code, target=target)
        if error:
            return error
        return success_response(
            "Script injected",
            details={
                "Identifier": result.get("identifier"),
                "Preview": result.get("code_preview"),
            },
        )

    # List mode
    result, error = rpc_call(state, "inject_list", target=target)
    if error:
        return error

    injections = result.get("injections", {})
    if not injections:
        return info_response("Injections", fields={"Status": "No active injections"})

    rows = []
    for inj_id, info in injections.items():
        rows.append({"ID": inj_id, "Preview": info.get("code_preview", ""), "Target": info.get("target", "")})

    return table_response(title="Active Injections", rows=rows)


__all__ = ["inject"]
