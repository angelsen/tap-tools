"""Body fetching service for response content."""

import base64
import json
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from webtap.cdp import CDPSession

logger = logging.getLogger(__name__)


class BodyService:
    """Response body fetching and caching."""

    def __init__(self):
        """Initialize body service."""
        self.cdp: CDPSession | None = None
        self._body_cache: dict[str, dict] = {}

    def get_body(self, rowid: int, use_cache: bool = True) -> dict:
        """Fetch request or response body for an event.

        Automatically detects event type and fetches appropriate body:
        - Network.requestWillBeSent: request body (POST data)
        - Network.responseReceived: response body
        - Fetch.requestPaused: request or response body based on stage

        Args:
            rowid: Row ID from events table
            use_cache: Whether to use cached body if available

        Returns:
            Dict with 'body' (str), 'base64Encoded' (bool), and 'event' (dict), or 'error' (str)
        """
        if not self.cdp:
            return {"error": "No CDP session"}

        # Get event from DB to extract requestId and method
        result = self.cdp.query("SELECT event FROM events WHERE rowid = ?", [rowid])

        if not result:
            return {"error": f"Event with rowid {rowid} not found"}

        try:
            event_data = json.loads(result[0][0])
        except json.JSONDecodeError:
            return {"error": "Failed to parse event data"}

        method = event_data.get("method", "")
        params = event_data.get("params", {})
        request_id = params.get("requestId")

        if not request_id:
            return {"error": "No requestId in event"}

        # Check cache first (cache includes event_data)
        cache_key = f"{request_id}:{method}"
        if use_cache and cache_key in self._body_cache:
            logger.debug(f"Using cached body for {cache_key}")
            return self._body_cache[cache_key]

        # Handle request body (POST data)
        if method == "Network.requestWillBeSent":
            request = params.get("request", {})

            # Check inline postData first (may be present for small bodies)
            if request.get("postData"):
                logger.debug(f"Using inline postData for {request_id}")
                body_data = {"body": request["postData"], "base64Encoded": False, "event": event_data}
                if use_cache:
                    self._body_cache[cache_key] = body_data
                return body_data

            # Check if request has POST data
            if not request.get("hasPostData"):
                return {"error": "No POST data in this request (GET or no body)"}

            # Try to fetch POST data via CDP
            try:
                logger.debug(f"Fetching POST data for {request_id} using Network.getRequestPostData")
                result = self.cdp.execute("Network.getRequestPostData", {"requestId": request_id})
                body_data = {"body": result.get("postData", ""), "base64Encoded": False, "event": event_data}

                if use_cache:
                    self._body_cache[cache_key] = body_data
                    logger.debug(f"Cached POST data for {request_id}")

                return body_data

            except Exception as e:
                error_msg = str(e)
                logger.error(f"Failed to fetch POST data for {request_id}: {error_msg}")
                # Provide helpful error message
                if "No resource with given identifier found" in error_msg:
                    return {"error": "POST data not available (possibly too large or not captured by CDP)"}
                return {"error": f"Failed to fetch POST data: {error_msg}"}

        # Handle response body
        elif method == "Fetch.requestPaused":
            # Fetch interception - verify it's response stage
            if "responseStatusCode" not in params:
                return {"error": "Not a response stage event (no responseStatusCode)"}
            domain = "Fetch"

        elif method == "Network.responseReceived":
            # Regular network response
            domain = "Network"

        else:
            # Unknown event type - return empty body but include event for expr access
            logger.debug(f"Unknown event type {method} - returning empty body with event data")
            return {"body": "", "base64Encoded": False, "event": event_data}

        # Fetch response body from CDP
        try:
            logger.debug(f"Fetching response body for {request_id} using {domain}.getResponseBody")
            result = self.cdp.execute(f"{domain}.getResponseBody", {"requestId": request_id})

            body_data = {
                "body": result.get("body", ""),
                "base64Encoded": result.get("base64Encoded", False),
                "event": event_data,
            }

            # Cache it
            if use_cache:
                self._body_cache[cache_key] = body_data
                logger.debug(f"Cached response body for {request_id}")

            return body_data

        except Exception as e:
            logger.error(f"Failed to fetch response body for {request_id}: {e}")
            return {"error": str(e)}

    def clear_cache(self):
        """Clear all cached bodies."""
        count = len(self._body_cache)
        self._body_cache.clear()
        logger.info(f"Cleared {count} cached bodies")
        return count

    def decode_body(self, body_content: str, is_base64: bool) -> str | bytes:
        """Decode body content if base64 encoded.

        Args:
            body_content: The body content (possibly base64)
            is_base64: Whether the content is base64 encoded
        """
        if not is_base64:
            return body_content

        try:
            decoded = base64.b64decode(body_content)
            # Try to decode as UTF-8 text
            try:
                return decoded.decode("utf-8")
            except UnicodeDecodeError:
                # Return as bytes for binary content
                return decoded
        except Exception as e:
            logger.error(f"Failed to decode base64 body: {e}")
            return body_content  # Return original if decode fails

    def prepare_for_generation(
        self,
        event: int,
        json_path: str = None,  # pyright: ignore[reportArgumentType]
        expr: str = None,  # pyright: ignore[reportArgumentType]
    ) -> dict:
        """Prepare HTTP body for code generation.

        Orchestrates the complete pipeline:
        1. Fetch body + event from CDP
        2. Decode base64 if needed
        3. Transform via expression OR validate and parse JSON
        4. Extract nested data via json_path
        5. Validate data structure (dict/list)

        Args:
            event: Event row ID from network() or events()
            json_path: Optional JSON path for nested extraction (e.g., "data[0]")
            expr: Optional Python expression with 'body' and 'event' variables

        Returns:
            Dict with 'data' (dict|list) on success, or 'error' (str) on failure.
            May include 'suggestions' (list[str]) for error guidance.

        Examples:
            result = body_service.prepare_for_generation(123, json_path="data[0]")
            if result.get("error"):
                return error_response(result["error"], suggestions=result.get("suggestions"))
            data = result["data"]
        """
        # 1. Fetch body + event from CDP
        result = self.get_body(event, use_cache=True)
        if "error" in result:
            return {"error": result["error"], "suggestions": [], "data": None}

        body_content = result["body"]
        is_base64 = result["base64Encoded"]
        event_data = result["event"]

        # 2. Decode if base64
        if is_base64:
            decoded = self.decode_body(body_content, is_base64)
            if isinstance(decoded, bytes):
                return {
                    "error": "Body is binary content",
                    "suggestions": [
                        "Only text/JSON can be converted to code",
                        "Try a different event with text content",
                    ],
                    "data": None,
                }
            body_content = decoded

        # 3. Transform via expression OR validate and parse JSON
        if expr:
            # Use expression evaluation from _utils
            from webtap.commands._utils import evaluate_expression

            try:
                namespace = {"body": body_content, "event": event_data}
                data, _ = evaluate_expression(expr, namespace)
            except Exception as e:
                return {
                    "error": f"Expression evaluation failed: {e}",
                    "suggestions": [
                        "Check your expression syntax",
                        "Variables available: 'body' (str), 'event' (dict)",
                        "Example: dict(urllib.parse.parse_qsl(body))",
                        "Example: json.loads(body)['data'][0]",
                    ],
                    "data": None,
                }
        else:
            # Validate body is not empty before parsing
            if not body_content.strip():
                return {
                    "error": "Body is empty",
                    "suggestions": [
                        "Use expr to extract data from event for non-HTTP events",
                        "Example: expr=\"json.loads(event['params']['response']['payloadData'])\"",
                        "Check the event structure with inspect() first",
                    ],
                    "data": None,
                }

            # Parse as JSON
            from webtap.commands._code_generation import parse_json

            data, error = parse_json(body_content)
            if error:
                return {
                    "error": error,
                    "suggestions": [
                        "Body must be valid JSON or use expr to transform it",
                        'For form data: expr="dict(urllib.parse.parse_qsl(body))"',
                        "Check the body with body() command first",
                    ],
                    "data": None,
                }

        # 4. Extract nested path if specified
        if json_path:
            from webtap.commands._code_generation import extract_json_path

            data, error = extract_json_path(data, json_path)
            if error:
                return {
                    "error": error,
                    "suggestions": [
                        f"Path '{json_path}' not found in body",
                        "Check the body structure with body() command",
                        'Try a simpler path like "data" or "data[0]"',
                    ],
                    "data": None,
                }

        # 5. Validate structure
        from webtap.commands._code_generation import validate_generation_data

        is_valid, error = validate_generation_data(data)
        if not is_valid:
            return {
                "error": error,
                "suggestions": [
                    "Code generation requires dict or list structure",
                    "Adjust json_path to extract a complex object",
                    "Or use expr to transform data into dict/list",
                ],
                "data": None,
            }

        return {"data": data, "error": None, "suggestions": []}
