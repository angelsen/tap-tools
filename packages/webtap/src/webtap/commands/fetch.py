"""HTTP fetch request interception with declarative rules."""

from webtap.app import app
from webtap.commands._builders import info_response, rpc_call

_fetch_desc = """Control fetch interception with declarative rules for body capture, blocking, and mocking.

Capture is enabled by default on connect. Block/mock rules are per-target.

Examples:
  fetch()                                    # Show capture state + per-target rules
  fetch({"capture": False})                  # Disable capture globally
  fetch({"capture": True})                   # Re-enable capture globally
  fetch({"mock": {"*api*": '{"ok":1}'}, "target": "9222:abc"})  # Mock for target
  fetch({"block": ["*tracking*"], "target": "9222:abc"})        # Block for target
  fetch({"target": "9222:abc"})              # Clear rules for target
"""


@app.command(
    display="markdown",
    typer={"enabled": False},
    fastmcp={"type": "tool", "mime_type": "text/markdown", "description": _fetch_desc},
)
def fetch(state, rules: dict = None) -> dict:  # pyright: ignore[reportArgumentType]
    """Control fetch interception with declarative rules.

    Capture is enabled by default on connect. Block/mock rules are per-target.

    Args:
        rules: Dict with rules (None to show status)
            - None - Show current status
            - {"capture": False} - Disable capture globally
            - {"capture": True} - Re-enable capture globally
            - {"block": [...], "target": "..."} - Set block rules for target
            - {"mock": {...}, "target": "..."} - Set mock rules for target
            - {"target": "..."} - Clear rules for target

    Examples:
        fetch()                                    # Show status
        fetch({"capture": False})                  # Disable capture
        fetch({"mock": {"*api*": "..."}, "target": "9222:abc"})  # Mock
        fetch({"block": ["*tracking*"], "target": "9222:abc"})   # Block

    Returns:
        Fetch interception status
    """
    # Call unified RPC method
    result, error = rpc_call(state, "fetch", rules=rules)
    if error:
        return error

    # Format response based on result
    capture = result.get("capture", True)
    capture_count = result.get("capture_count", 0)
    rules_by_target = result.get("rules", {})

    fields = {"Capture": f"{'On' if capture else 'Off'} ({capture_count} bodies)"}

    # Add per-target rules if any
    for target, target_rules in rules_by_target.items():
        block = target_rules.get("block", [])
        mock = target_rules.get("mock", {})
        parts = []
        if block:
            parts.append(f"{len(block)} block")
        if mock:
            parts.append(f"{len(mock)} mock")
        if parts:
            fields[target] = ", ".join(parts)

    title = f"Fetch: Capture {'On' if capture else 'Off'}"
    return info_response(title=title, fields=fields)


__all__ = ["fetch"]
