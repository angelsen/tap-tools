"""Screenshot capture for watched browser targets.

Commands: screenshot (resource), screenshot_capture (tool)
"""

import base64
import time
from pathlib import Path

from webtap.app import app
from webtap.commands._builders import info_response, rpc_call, success_response
from webtap.commands._code_generation import ensure_output_directory

_SCREENSHOT_DIR = Path("/tmp/webtap")

_DOM_TYPES = {"page", "background_page"}

_TYPE_LABELS = {
    "page": "page",
    "service_worker": "sw",
    "background_page": "bg",
    "worker": "worker",
}


@app.command(
    display="markdown",
    fastmcp={"type": "resource", "mime_type": "text/plain"},
)
def screenshot(state) -> dict:
    """Screenshot capability with current watched targets.

    Attach this resource to provide visual context. Lists targets
    available for screenshot capture via screenshot_capture tool.

    Returns:
        Text describing available targets and usage
    """
    result, error = rpc_call(state, "targets")
    if error:
        return error

    targets_list = result.get("targets", [])
    watched = [
        t
        for t in targets_list
        if (t.get("watched") or t.get("auto_attached"))
        and t.get("type") in _DOM_TYPES
        and t.get("state") in ("attached", "inspecting")
    ]

    lines = ["# Screenshot", ""]

    if not watched:
        lines.append("No watched targets with DOM available for screenshot.")
        lines.append("")
        lines.append("Watch a target first: `watch(['9222:abc'])`")
    else:
        lines.append("Available targets:")
        lines.append("")
        for t in watched:
            target_id = t.get("target", "")
            type_label = _TYPE_LABELS.get(t.get("type", ""), t.get("type", ""))
            title = t.get("title", "Untitled")
            url = t.get("url", "")
            lines.append(f"  {target_id} [{type_label}] {title}")
            lines.append(f"    {url}")
        lines.append("")
        lines.append("Capture with screenshot_capture tool:")
        example_target = watched[0].get("target", "")
        lines.append(f'  screenshot_capture("{example_target}")')
        lines.append(f'  screenshot_capture("{example_target}", full_page=True)')

    return info_response(extra="\n".join(lines))


@app.command(
    display="markdown",
    fastmcp={"type": "tool", "mime_type": "text/markdown"},
)
def screenshot_capture(
    state,
    target: str,
    output: str = None,  # pyright: ignore[reportArgumentType]
    format: str = "png",
    quality: int = None,  # pyright: ignore[reportArgumentType]
    full_page: bool = False,
) -> dict:
    """Capture viewport screenshot of a browser target and save to file.

    Args:
        target: Target ID (e.g., "9222:abc123")
        output: File path to save screenshot. Defaults to /tmp/webtap/screenshot-{timestamp}.{format}
        format: Image format - "png", "jpeg", or "webp". Defaults to "png".
        quality: Compression quality 0-100 (jpeg only). Defaults to None.
        full_page: Capture full scrollable page, not just viewport. Defaults to False.

    Examples:
        screenshot_capture("9222:abc")                        # Viewport to /tmp/webtap/
        screenshot_capture("9222:abc", full_page=True)        # Full page
        screenshot_capture("9222:abc", "captures/page.png")   # Custom path
        screenshot_capture("9222:abc", format="jpeg", quality=80)
    """
    result, error = rpc_call(state, "screenshot", target=target, format=format, quality=quality, full_page=full_page)
    if error:
        return error

    image_data = base64.b64decode(result["data"])

    if output:
        output_path = ensure_output_directory(output)
    else:
        _SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = int(time.time() * 1000)
        output_path = _SCREENSHOT_DIR / f"screenshot-{timestamp}.{format}"

    output_path.write_bytes(image_data)

    details = {
        "Output": str(output_path),
        "Size": f"{len(image_data)} bytes",
        "Format": format,
    }
    if full_page:
        details["Mode"] = "full page"

    return success_response("Screenshot saved", details=details)
