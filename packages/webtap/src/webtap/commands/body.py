"""HTTP response body inspection and analysis commands."""

import json
from webtap.app import app
from webtap.commands._utils import evaluate_expression, format_expression_result
from webtap.commands._builders import check_connection, info_response, error_response
from webtap.commands._tips import get_mcp_description


mcp_desc = get_mcp_description("body")


@app.command(display="markdown", fastmcp={"type": "tool", "description": mcp_desc} if mcp_desc else {"type": "tool"})
def body(state, event: int, expr: str = None, decode: bool = True, cache: bool = True) -> dict:  # pyright: ignore[reportArgumentType]
    """Fetch and analyze request or response body with Python expressions.

    Automatically detects event type and fetches appropriate body:
    - Request events (Network.requestWillBeSent): POST/PUT/PATCH request body
    - Response events (Network.responseReceived): response body

    Args:
        event: Event row ID from network(), events(), or requests()
        expr: Optional Python expression with 'body' variable
        decode: Auto-decode base64 (default: True)
        cache: Use cached body (default: True)

    Returns:
        Body content or expression result
    """
    if error := check_connection(state):
        return error

    # Get body from service (with optional caching)
    body_service = state.service.body
    result = body_service.get_body(event, use_cache=cache)

    if "error" in result:
        return error_response(result["error"])

    body_content = result.get("body", "")
    is_base64 = result.get("base64Encoded", False)

    # Handle base64 decoding if requested
    if is_base64 and decode:
        decoded = body_service.decode_body(body_content, is_base64)
        if isinstance(decoded, bytes):
            # Binary content - can't show directly
            if not expr:
                return info_response(
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
            return info_response(
                title="Response Body", fields={"Type": "Binary content", "Size": f"{len(body_content)} bytes"}
            )

        # Build markdown response with body in code block
        # DATA-LEVEL TRUNCATION for memory/performance (as per refactor plan)
        MAX_BODY_SIZE = 5000  # Keep data-level truncation for large bodies
        elements = [{"type": "heading", "content": "Body", "level": 2}]

        # Try to detect content type and format appropriately
        content_preview = body_content[:100]
        if content_preview.strip().startswith("{") or content_preview.strip().startswith("["):
            # Likely JSON
            try:
                parsed = json.loads(body_content)
                formatted = json.dumps(parsed, indent=2)
                if len(formatted) > MAX_BODY_SIZE:
                    elements.append({"type": "code_block", "content": formatted[:MAX_BODY_SIZE], "language": "json"})
                    elements.append(
                        {"type": "text", "content": f"_[truncated at {MAX_BODY_SIZE} chars, {len(formatted)} total]_"}
                    )
                else:
                    elements.append({"type": "code_block", "content": formatted, "language": "json"})
            except (json.JSONDecodeError, ValueError):
                # Not valid JSON, show as text
                if len(body_content) > MAX_BODY_SIZE:
                    elements.append({"type": "code_block", "content": body_content[:MAX_BODY_SIZE], "language": ""})
                    elements.append(
                        {
                            "type": "text",
                            "content": f"_[truncated at {MAX_BODY_SIZE} chars, {len(body_content)} total]_",
                        }
                    )
                else:
                    elements.append({"type": "code_block", "content": body_content, "language": ""})
        elif content_preview.strip().startswith("<"):
            # Likely HTML/XML
            if len(body_content) > MAX_BODY_SIZE:
                elements.append({"type": "code_block", "content": body_content[:MAX_BODY_SIZE], "language": "html"})
                elements.append(
                    {"type": "text", "content": f"_[truncated at {MAX_BODY_SIZE} chars, {len(body_content)} total]_"}
                )
            else:
                elements.append({"type": "code_block", "content": body_content, "language": "html"})
        else:
            # Plain text or unknown
            if len(body_content) > MAX_BODY_SIZE:
                elements.append({"type": "code_block", "content": body_content[:MAX_BODY_SIZE], "language": ""})
                elements.append(
                    {"type": "text", "content": f"_[truncated at {MAX_BODY_SIZE} chars, {len(body_content)} total]_"}
                )
            else:
                elements.append({"type": "code_block", "content": body_content, "language": ""})

        elements.append({"type": "text", "content": f"\n**Size:** {len(body_content)} characters"})
        return {"elements": elements}

    # Evaluate expression with body available
    try:
        namespace = {"body": body_content}
        result, output = evaluate_expression(expr, namespace)
        formatted_result = format_expression_result(result, output)

        # Build markdown response
        return {
            "elements": [
                {"type": "heading", "content": "Expression Result", "level": 2},
                {"type": "code_block", "content": expr, "language": "python"},
                {"type": "text", "content": "**Result:**"},
                {"type": "code_block", "content": formatted_result, "language": ""},
            ]
        }
    except Exception as e:
        # Provide helpful suggestions based on the error type
        suggestions = ["The body is available as 'body' variable"]

        if "NameError" in str(type(e).__name__):
            suggestions.extend(
                [
                    "Common libraries are pre-imported: re, json, bs4, jwt, httpx",
                    "Example: bs4(body, 'html.parser').find('title')",
                ]
            )
        elif "JSONDecodeError" in str(e):
            suggestions.extend(
                [
                    "Body might not be valid JSON. Try: type(body) to check",
                    "For HTML, use: bs4(body, 'html.parser')",
                ]
            )
        elif "KeyError" in str(e):
            suggestions.extend(
                [
                    "Key not found. Try: json.loads(body).keys() to see available keys",
                    "Use .get() for safe access: data.get('key', 'default')",
                ]
            )

        return error_response(f"{type(e).__name__}: {e}", suggestions=suggestions)
