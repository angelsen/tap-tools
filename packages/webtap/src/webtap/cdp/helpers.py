"""Helper functions for CDP event processing.

Extract and format data from CDP events for display.
"""


def build_network_row(request_id: str, events: list[dict]) -> dict:
    """Build table row from CDP network events.

    Network requests have multiple events that need correlation:
    - Network.requestWillBeSent: request details
    - Network.responseReceived: response details
    - Network.loadingFinished: final size
    - Network.loadingFailed: error state

    Returns:
        Dict with fields for table display
    """
    row = {
        "id": request_id,
        "method": "",
        "status": None,
        "url": "",
        "type": None,
        "size": None,
        "_events": events,  # Keep full CDP events for detail view
    }

    # Extract data from each event type
    for event in events:
        method = event.get("method", "")
        params = event.get("params", {})

        if method == "Network.requestWillBeSent":
            # Request details
            request = params.get("request", {})
            row["url"] = request.get("url", "")
            row["method"] = request.get("method", "")

        elif method == "Network.responseReceived":
            # Response details
            response = params.get("response", {})
            row["status"] = response.get("status")

            # Use CDP's resource type directly
            row["type"] = params.get("type")

        elif method == "Network.loadingFinished":
            # Final size
            row["size"] = params.get("encodedDataLength", 0)

        elif method == "Network.loadingFailed":
            # Failed requests have no status - keep as None
            pass

    return row


def build_console_row(event: dict) -> dict:
    """Build table row from CDP console event.

    Console events are simpler - one event per message.

    Returns:
        Dict with fields for table display
    """
    method = event.get("method", "")
    params = event.get("params", {})

    if method == "Runtime.consoleAPICalled":
        # JavaScript console.* call
        # Extract message from first argument
        args = params.get("args", [])
        message = _extract_console_message(args)

        return {
            "id": str(params.get("timestamp", id(event))),
            "level": params.get("type", "log"),  # log, debug, info, error, warning
            "message": message,
            "source": "console",
            "_event": event,  # Keep full CDP event for detail view
        }

    elif method == "Log.entryAdded":
        # Browser log entry
        entry = params.get("entry", {})

        return {
            "id": str(entry.get("timestamp", id(event))),
            "level": entry.get("level", "info"),  # verbose, info, warning, error
            "message": entry.get("text", ""),
            "source": entry.get("source", "other"),  # xml, javascript, network, etc.
            "_event": event,  # Keep full CDP event for detail view
        }

    # Shouldn't happen, but handle gracefully
    return {"id": str(id(event)), "level": "info", "message": str(event)[:100], "source": "unknown", "_event": event}


def _extract_console_message(args: list[dict]) -> str:
    """Extract message from console arguments - use CDP's representation.

    CDP already provides description or value for most cases.
    """
    if not args:
        return ""

    # Use first argument's description or value - CDP already formatted it
    first_arg = args[0]

    # CDP provides description for objects, or value for primitives
    if "description" in first_arg:
        return first_arg["description"]
    elif "value" in first_arg:
        return str(first_arg["value"])
    else:
        # Fallback to type
        return f"[{first_arg.get('type', 'unknown')}]"


def format_size(bytes_val: int | None) -> str:
    """Format bytes as human-readable string for display."""
    if bytes_val is None:
        return "-"

    if bytes_val == 0:
        return "0"

    size = float(bytes_val)
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            if unit == "B":
                return f"{int(size)}"
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"


def truncate_url(url: str, max_length: int = 60) -> str:
    """Truncate URL for table display, keeping important parts."""
    if len(url) <= max_length:
        return url

    # Try to keep domain and end of path
    if "://" in url:
        parts = url.split("://", 1)
        protocol = parts[0]
        rest = parts[1]

        if "/" in rest:
            domain, path = rest.split("/", 1)
            # Keep protocol, domain, and end of path
            available = max_length - len(protocol) - 3 - len(domain) - 4  # "://" + "..." + "/"
            if available > 10:
                return f"{protocol}://{domain}/...{path[-(available):]}"

    # Fallback to simple truncation
    return url[: max_length - 3] + "..."
