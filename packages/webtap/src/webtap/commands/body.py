"""Response body inspection command."""

import json
from webtap.app import app
from webtap.commands._utils import evaluate_expression, format_expression_result, build_info_response
from webtap.commands._errors import check_connection, error_response
from replkit2.textkit import markdown


@app.command(display="markdown")
def body(state, response: int, expr: str | None = None, decode: bool = True, cache: bool = True) -> dict:
    """Fetch and optionally process response body.

    Fetches the response body for any network response event.
    Works with both regular Network.responseReceived events (from network() command)
    and Fetch.requestPaused events (from requests() command).
    Bodies are cached per requestId to avoid refetching when running multiple
    expressions on the same response.

    Args:
        response: Row ID from network() or requests() table
        expr: Python expression to evaluate on body (body available as 'body')
        decode: Auto-decode base64 content if possible
        cache: Use cached body if available (default: True)

    Examples:
        body(49)                                # Get full body
        body(49, expr="len(body)")             # Get body length
        body(49, expr="body[:100]")            # First 100 chars

        # Parse JSON response
        body(49, expr="import json; json.loads(body)['data']")
        body(49, expr="import json; json.dumps(json.loads(body), indent=2)[:500]")

        # Extract with regex
        body(49, expr="import re; re.findall(r'<title>(.*?)</title>', body)")
        body(49, expr="import re; re.findall(r'/api/[^\"\\s]+', body)[:10]")  # Find API endpoints

        # Parse HTML with BeautifulSoup
        body(60, expr="from bs4 import BeautifulSoup; soup = BeautifulSoup(body, 'html.parser'); soup.title.text")
        body(60, expr="from bs4 import BeautifulSoup; soup = BeautifulSoup(body, 'html.parser'); len(soup.find_all('script'))")
        body(60, expr="from bs4 import BeautifulSoup; soup = BeautifulSoup(body, 'html.parser'); [s.get('src', 'inline')[:50] for s in soup.find_all('script')[:5]]")

        # Check content
        body(49, expr="'error' in body.lower()")
        body(49, expr="body.count('\\n')")  # Count lines

        # Force refetch (bypass cache)
        body(49, cache=False)

    Returns:
        Body content or expression result
    """
    if error := check_connection(state):
        return error

    # Get body from service (with optional caching)
    body_service = state.service.body
    result = body_service.get_response_body(response, use_cache=cache)

    if "error" in result:
        return error_response("custom", custom_message=result["error"])

    body_content = result.get("body", "")
    is_base64 = result.get("base64Encoded", False)

    # Handle base64 decoding if requested
    if is_base64 and decode:
        decoded = body_service.decode_body(body_content, is_base64)
        if isinstance(decoded, bytes):
            # Binary content - can't show directly
            if not expr:
                return build_info_response(
                    title="Response Body",
                    fields={
                        "Type": "Binary content",
                        "Size (base64)": f"{len(body_content)} bytes",
                        "Size (decoded)": f"{len(decoded)} bytes",
                    },
                )
            # For expressions, provide the bytes
            body_content = decoded
        else:
            # Successfully decoded to text
            body_content = decoded

    # No expression - return the body directly
    if not expr:
        if isinstance(body_content, bytes):
            return build_info_response(
                title="Response Body", fields={"Type": "Binary content", "Size": f"{len(body_content)} bytes"}
            )

        # Build markdown response with body in code block
        builder = markdown().heading("Response Body", level=2)

        # Try to detect content type and format appropriately
        content_preview = body_content[:100]
        if content_preview.strip().startswith("{") or content_preview.strip().startswith("["):
            # Likely JSON
            try:
                parsed = json.loads(body_content)
                builder.code_block(json.dumps(parsed, indent=2)[:5000], language="json")
                if len(body_content) > 5000:
                    builder.text(f"_[truncated, {len(body_content)} chars total]_")
            except (json.JSONDecodeError, ValueError):
                # Not valid JSON, show as text
                builder.code_block(body_content[:5000], language="")
                if len(body_content) > 5000:
                    builder.text(f"_[truncated, {len(body_content)} chars total]_")
        elif content_preview.strip().startswith("<"):
            # Likely HTML/XML
            builder.code_block(body_content[:5000], language="html")
            if len(body_content) > 5000:
                builder.text(f"_[truncated, {len(body_content)} chars total]_")
        else:
            # Plain text or unknown
            builder.code_block(body_content[:5000], language="")
            if len(body_content) > 5000:
                builder.text(f"_[truncated, {len(body_content)} chars total]_")

        builder.text(f"\n**Size:** {len(body_content)} characters")
        return builder.build()

    # Evaluate expression with body available
    try:
        namespace = {"body": body_content}
        result, output = evaluate_expression(expr, namespace)
        formatted_result = format_expression_result(result, output)

        # Build markdown response
        builder = markdown().heading("Expression Result", level=2)
        builder.code_block(expr, language="python")
        builder.text("**Result:**")
        builder.code_block(formatted_result, language="")
        return builder.build()
    except Exception as e:
        return error_response(
            "custom", custom_message=f"{type(e).__name__}: {e}", note="The body is available as 'body' variable"
        )
