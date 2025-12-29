"""Extension-side response body capture control."""

from webtap.app import app
from webtap.client import RPCError
from webtap.commands._builders import error_response, info_response


@app.command(display="markdown", fastmcp={"type": "tool", "mime_type": "text/markdown"})
def capture(state, action: str = "status") -> dict:
    """Control extension-side body capture.

    When enabled, response bodies are automatically captured before Chrome
    evicts them from memory. Zero latency impact - bodies are grabbed
    transparently and stored for later retrieval via request().

    Args:
        action: "enable", "disable", or "status"

    Examples:
        capture("enable")   # Start capturing
        capture("disable")  # Stop capturing
        capture()           # Check status

    Returns:
        Capture status in markdown
    """
    try:
        if action == "enable":
            state.client.call("capture.enable")
            return info_response(
                title="Capture Enabled",
                fields={"Status": "Response bodies will be captured automatically"},
            )

        elif action == "disable":
            state.client.call("capture.disable")
            return info_response(
                title="Capture Disabled",
                fields={"Status": "Response body capture stopped"},
            )

        else:
            snapshot = state.client.call("status")
            enabled = snapshot.get("fetch", {}).get("capture_enabled", False)
            return info_response(
                title="Capture Status",
                fields={"Capture": "Enabled" if enabled else "Disabled"},
            )

    except RPCError as e:
        return error_response(e.message)
    except Exception as e:
        return error_response(str(e))
