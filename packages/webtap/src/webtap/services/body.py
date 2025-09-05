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

    def get_response_body(self, rowid: int, use_cache: bool = True) -> dict:
        """Fetch response body for a response.

        Args:
            rowid: Row ID from events table (Network or Fetch response)
            use_cache: Whether to use cached body if available
        """
        if not self.cdp:
            return {"error": "No CDP session"}

        # Get event from DB to extract requestId
        result = self.cdp.query("SELECT event FROM events WHERE rowid = ?", [rowid])

        if not result:
            return {"error": f"Event with rowid {rowid} not found"}

        try:
            event_data = json.loads(result[0][0])
        except json.JSONDecodeError:
            return {"error": "Failed to parse event data"}

        method = event_data.get("method", "")
        params = event_data.get("params", {})

        # Handle both Fetch and Network events
        if method == "Fetch.requestPaused":
            # Fetch interception - verify it's response stage
            if "responseStatusCode" not in params:
                return {"error": "Not a response stage event (no responseStatusCode)"}
            request_id = params.get("requestId")
            domain = "Fetch"
        elif method == "Network.responseReceived":
            # Regular network response
            request_id = params.get("requestId")
            domain = "Network"
        else:
            return {"error": f"Not a response event (method: {method})"}

        if not request_id:
            return {"error": "No requestId in event"}

        # Check cache
        if use_cache and request_id in self._body_cache:
            logger.debug(f"Using cached body for {request_id}")
            return self._body_cache[request_id]

        try:
            # Fetch body from CDP using appropriate domain
            logger.debug(f"Fetching body for {request_id} using {domain}.getResponseBody")
            result = self.cdp.execute(f"{domain}.getResponseBody", {"requestId": request_id})

            body_data = {"body": result.get("body", ""), "base64Encoded": result.get("base64Encoded", False)}

            # Cache it for this request
            if use_cache:
                self._body_cache[request_id] = body_data
                logger.debug(f"Cached body for {request_id}")

            return body_data

        except Exception as e:
            logger.error(f"Failed to fetch body for {request_id}: {e}")
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
