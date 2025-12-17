"""Network monitoring service using HAR views.

PUBLIC API:
  - NetworkService: HAR-based network request queries
"""

import json
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from webtap.cdp import CDPSession
    from webtap.filters import FilterManager

logger = logging.getLogger(__name__)


class NetworkService:
    """Network event queries using HAR views."""

    def __init__(self):
        """Initialize network service."""
        self.cdp: CDPSession | None = None
        self.filters: FilterManager | None = None

    @property
    def request_count(self) -> int:
        """Count of all network requests."""
        if not self.cdp:
            return 0
        result = self.cdp.query("SELECT COUNT(*) FROM har_summary")
        return result[0][0] if result else 0

    def get_requests(
        self,
        limit: int = 20,
        status: int | None = None,
        method: str | None = None,
        type_filter: str | None = None,
        url: str | None = None,
        apply_groups: bool = True,
        order: str = "desc",
    ) -> list[dict]:
        """Get network requests from HAR summary view.

        Args:
            limit: Maximum results.
            status: Filter by HTTP status code.
            method: Filter by HTTP method.
            type_filter: Filter by resource type.
            url: Filter by URL pattern (supports * wildcard).
            apply_groups: Apply enabled filter groups.
            order: Sort order - "desc" (newest first) or "asc" (oldest first).

        Returns:
            List of request summary dicts.
        """
        if not self.cdp:
            return []

        # Build SQL query
        sql = """
        SELECT
            id,
            request_id,
            protocol,
            method,
            status,
            url,
            type,
            size,
            time_ms,
            state,
            frames_sent,
            frames_received
        FROM har_summary
        """

        # Build filter conditions
        conditions = ""
        if self.filters:
            conditions = self.filters.build_filter_sql(
                status=status,
                method=method,
                type_filter=type_filter,
                url=url,
                apply_groups=apply_groups,
            )

        if conditions:
            sql += f" WHERE {conditions}"

        sort_dir = "ASC" if order.lower() == "asc" else "DESC"
        sql += f" ORDER BY id {sort_dir} LIMIT {limit}"

        # Execute query and convert to dicts
        rows = self.cdp.query(sql)
        columns = [
            "id",
            "request_id",
            "protocol",
            "method",
            "status",
            "url",
            "type",
            "size",
            "time_ms",
            "state",
            "frames_sent",
            "frames_received",
        ]

        return [dict(zip(columns, row)) for row in rows]

    def get_request_details(self, row_id: int) -> dict | None:
        """Get HAR entry with proper nested structure.

        Args:
            row_id: Row ID from har_summary.

        Returns:
            HAR-structured dict or None if not found.

        Structure matches HAR spec:
            {
                "id": 123,
                "request": {"method", "url", "headers", "postData"},
                "response": {"status", "statusText", "headers", "content"},
                "time": 150,
                "state": "complete",
                ...
            }
        """
        if not self.cdp:
            return None

        sql = """
        SELECT
            id,
            request_id,
            protocol,
            method,
            url,
            status,
            status_text,
            type,
            size,
            time_ms,
            state,
            request_headers,
            post_data,
            response_headers,
            mime_type,
            timing,
            error_text,
            frames_sent,
            frames_received,
            ws_total_bytes
        FROM har_entries
        WHERE id = ?
        """

        rows = self.cdp.query(sql, [row_id])
        if not rows:
            return None

        row = rows[0]
        columns = [
            "id",
            "request_id",
            "protocol",
            "method",
            "url",
            "status",
            "status_text",
            "type",
            "size",
            "time_ms",
            "state",
            "request_headers",
            "post_data",
            "response_headers",
            "mime_type",
            "timing",
            "error_text",
            "frames_sent",
            "frames_received",
            "ws_total_bytes",
        ]
        flat = dict(zip(columns, row))

        # Parse JSON fields
        def parse_json(val):
            if val and isinstance(val, str):
                try:
                    return json.loads(val)
                except json.JSONDecodeError:
                    return val
            return val

        # Build HAR-nested structure
        har: dict = {
            "id": flat["id"],
            "request_id": flat["request_id"],
            "protocol": flat["protocol"],
            "type": flat["type"],
            "time": flat["time_ms"],
            "state": flat["state"],
            "request": {
                "method": flat["method"],
                "url": flat["url"],
                "headers": parse_json(flat["request_headers"]) or {},
                "postData": flat["post_data"],
            },
            "response": {
                "status": flat["status"],
                "statusText": flat["status_text"],
                "headers": parse_json(flat["response_headers"]) or {},
                "content": {
                    "size": flat["size"],
                    "mimeType": flat["mime_type"],
                },
            },
            "timings": parse_json(flat["timing"]),
        }

        # Add error if failed
        if flat["error_text"]:
            har["error"] = flat["error_text"]

        # Add WebSocket stats if applicable
        if flat["protocol"] == "websocket":
            har["websocket"] = {
                "framesSent": flat["frames_sent"],
                "framesReceived": flat["frames_received"],
                "totalBytes": flat["ws_total_bytes"],
            }

        return har

    def fetch_body(self, request_id: str) -> dict | None:
        """Fetch response body for a request.

        Args:
            request_id: CDP request ID.

        Returns:
            Dict with 'body' and 'base64Encoded' keys, or None.
        """
        if not self.cdp:
            return None
        return self.cdp.fetch_body(request_id)

    def get_request_by_row_id(self, row_id: int) -> str | None:
        """Get request_id for a row ID.

        Args:
            row_id: Row ID from har_summary.

        Returns:
            CDP request ID or None.
        """
        if not self.cdp:
            return None

        result = self.cdp.query("SELECT request_id FROM har_summary WHERE id = ?", [row_id])
        return result[0][0] if result else None


__all__ = ["NetworkService"]
