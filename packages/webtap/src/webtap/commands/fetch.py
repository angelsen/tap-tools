"""HTTP fetch request interception with declarative rules."""

from webtap.app import app
from webtap.commands._builders import info_response, rpc_call

_fetch_desc = """Control fetch interception with declarative rules for body capture, blocking, and mocking.

Examples:
  fetch({"capture": True})                    # Capture all response bodies
  fetch({"block": ["*tracking*", "*ads*"]})  # Block matching URLs
  fetch({"mock": {"*api*": '{"ok":1}'}})     # Mock responses
  fetch({"capture": True, "block": ["*ads*"]}) # Combine rules
  fetch({})                                   # Disable all rules
  fetch()                                     # Show current rules
"""


@app.command(
    display="markdown",
    typer={"enabled": False},
    fastmcp={"type": "tool", "mime_type": "text/markdown", "description": _fetch_desc},
)
def fetch(state, rules: dict = None) -> dict:  # pyright: ignore[reportArgumentType]
    """Control fetch interception with declarative rules.

    Args:
        rules: Dict with rules (None to show status)
            - {"capture": True} - Capture all response bodies
            - {"block": ["*pattern*"]} - Block matching URLs
            - {"mock": {"*pattern*": "body"}} - Mock matching URLs
            - {} - Disable all rules
            - None - Show current status

    Examples:
        fetch({"capture": True})                    # Capture bodies
        fetch({"block": ["*tracking*", "*ads*"]})  # Block patterns
        fetch({"mock": {"*api*": '{"ok":1}'}})     # Mock responses
        fetch({"capture": True, "block": ["*ads*"]}) # Combine
        fetch({})                                   # Disable
        fetch()                                     # Show status

    Returns:
        Fetch interception status
    """
    # Status check (None = show status)
    if rules is None:
        status, error = rpc_call(state, "status")
        if error:
            return error

        fetch_state = status.get("fetch", {})
        fetch_enabled = fetch_state.get("enabled", False)

        if not fetch_enabled:
            return info_response(title="Fetch Status: Disabled", fields={"Status": "Interception disabled"})

        fetch_rules = fetch_state.get("rules", {})
        capture_count = fetch_state.get("capture_count", 0)

        fields = {"Status": "Enabled"}
        if fetch_rules.get("capture"):
            fields["Capture"] = f"On ({capture_count} bodies)"
        if fetch_rules.get("block"):
            fields["Block"] = f"{len(fetch_rules['block'])} patterns"
        if fetch_rules.get("mock"):
            fields["Mock"] = f"{len(fetch_rules['mock'])} patterns"

        return info_response(title="Fetch Status: Enabled", fields=fields)

    # Disable if empty dict
    if not rules:
        _, error = rpc_call(state, "fetch.disable")
        if error:
            return error
        return info_response(title="Fetch Disabled", fields={"Status": "Interception disabled"})

    # Enable with rules
    result, error = rpc_call(state, "fetch.enable", rules=rules)
    if error:
        return error

    enabled_rules = result.get("rules", {})
    fields = {"Status": "Enabled"}

    if enabled_rules.get("capture"):
        fields["Capture"] = "On"
    if enabled_rules.get("block"):
        fields["Block"] = f"{len(enabled_rules['block'])} patterns"
    if enabled_rules.get("mock"):
        fields["Mock"] = f"{len(enabled_rules['mock'])} patterns"

    return info_response(title="Fetch Enabled", fields=fields)


__all__ = ["fetch"]
