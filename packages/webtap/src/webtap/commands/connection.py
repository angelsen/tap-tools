"""Connection management commands."""

from webtap.app import app


# Required CDP domains for WebTap functionality
REQUIRED_DOMAINS = [
    "Page",  # Navigation, lifecycle, history
    "Network",  # Request/response monitoring
    "Runtime",  # Console API, JavaScript execution
    "Log",  # Browser logs (errors, warnings)
    "DOMStorage",  # localStorage/sessionStorage events
]


@app.command(display="markdown")
def connect(state, page: int) -> dict:
    """Connect to Chrome page and enable all required domains.

    Args:
        page: Page index to connect to

    Returns:
        Connection status in markdown
    """
    # Connect to Chrome
    state.cdp.connect(page)

    # Enable ALL required domains - fail if any don't work
    failures = []

    for domain in REQUIRED_DOMAINS:
        try:
            state.cdp.execute(f"{domain}.enable")
        except Exception as e:
            failures.append(f"{domain}: {e}")

    # Note: Storage domain doesn't need explicit enable - getCookies works directly

    if failures:
        # Disconnect and report failure
        state.cdp.disconnect()
        raise RuntimeError("Failed to enable required domains:\n" + "\n".join(failures))

    # Success - return markdown
    page_info = state.cdp.page_info
    title = page_info.get("title", "Untitled") if page_info else "Unknown"
    url = page_info.get("url", "") if page_info else ""

    return {
        "elements": [
            {"type": "heading", "content": f"Connected to: {title}", "level": 2},
            {"type": "text", "content": url},
        ]
    }


@app.command()
def disconnect(state) -> str:
    """Disconnect from Chrome."""
    if not state.cdp.connected.is_set():
        return "Not connected"

    state.cdp.disconnect()
    return "Disconnected"


@app.command(display="table", headers=["Index", "Title", "URL", "Type"])
def pages(state) -> list[dict]:
    """List available Chrome pages.

    Returns:
        Table of available pages
    """
    pages_list = state.cdp.list_pages()

    # Format for table display
    return [
        {
            "Index": str(i),
            "Title": p.get("title", "Untitled")[:40] + "..."
            if len(p.get("title", "")) > 40
            else p.get("title", "Untitled"),
            "URL": p.get("url", "")[:50] + "..." if len(p.get("url", "")) > 50 else p.get("url", ""),
            "Type": p.get("type", "page"),
        }
        for i, p in enumerate(pages_list)
    ]


@app.command(display="markdown")
def status(state) -> dict:
    """Get connection status.

    Returns:
        Status information in markdown
    """
    connected = state.cdp.connected.is_set()

    if not connected:
        return {"elements": [{"type": "text", "content": "Not connected"}]}

    title = state.cdp.page_info.get("title", "Untitled") if state.cdp.page_info else "Unknown"
    url = state.cdp.page_info.get("url", "") if state.cdp.page_info else ""

    return {
        "elements": [
            {"type": "heading", "content": "Connection Status", "level": 2},
            {"type": "text", "content": f"**Page:** {title}"},
            {"type": "text", "content": f"**URL:** {url}"},
            {
                "type": "code_block",
                "content": f"Network events: {len(state.cdp.network_events)}\nConsole events: {len(state.cdp.console_events)}",
                "language": "",
            },
        ]
    }
