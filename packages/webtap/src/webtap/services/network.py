"""Network monitoring service using HAR views.

PUBLIC API:
  - NetworkService: Network event queries using HAR views
"""

import json
import logging
from typing import Any

from webtap.services._utils import aggregate_query, get_nested, set_nested

logger = logging.getLogger(__name__)


class NetworkService:
    """Network event queries using HAR views.

    Provides network request/response monitoring via CDP Network domain events
    aggregated into HAR (HTTP Archive) format views stored in DuckDB.

    Attributes:
        service: WebTapService reference for multi-target operations.
    """

    def __init__(self):
        """Initialize network service."""
        self.service: "Any" = None

    def set_service(self, service: "Any") -> None:
        """Set service reference.

        Args:
            service: WebTapService instance
        """
        self.service = service

    @property
    def request_count(self) -> int:
        """Count of all network requests across all connections."""
        if not self.service:
            return 0
        total = 0
        for conn in self.service.connections.values():
            try:
                result = conn.cdp.query("SELECT COUNT(*) FROM har_summary")
                total += result[0][0] if result else 0
            except Exception:
                pass
        return total

    def get_requests(
        self,
        targets: list[str] | None = None,
        limit: int = 20,
        status: int | None = None,
        method: str | None = None,
        type_filter: str | None = None,
        url: str | None = None,
        state: str | None = None,
        apply_groups: bool = True,
        order: str = "desc",
        target: str | list[str] | None = None,
    ) -> list[dict]:
        """Get network requests from HAR summary view, aggregated from multiple targets.

        Args:
            targets: Explicit target list, or None for tracked/all
            limit: Maximum results.
            status: Filter by HTTP status code.
            method: Filter by HTTP method.
            type_filter: Filter by resource type.
            url: Filter by URL pattern (supports * wildcard).
            state: Filter by state (pending, loading, complete, failed, paused).
            apply_groups: Apply enabled filter groups.
            order: Sort order - "desc" (newest first) or "asc" (oldest first).
            target: Legacy parameter - use targets instead

        Returns:
            List of request summary dicts with target field.
        """
        if not self.service:
            return []

        # Use targets parameter (new) or target (legacy)
        if targets is None and target is not None:
            targets = [target] if isinstance(target, str) else target

        # Get CDPSessions for specified or tracked/all targets
        cdps = self.service.get_cdps(targets)
        if not cdps:
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
            pause_stage,
            paused_id,
            frames_sent,
            frames_received,
            started_datetime,
            last_activity,
            target,
            body_status
        FROM har_summary
        """

        # Build filter conditions (without target filter - we handle that via get_cdps)
        conditions = ""
        if self.service and self.service.filters:
            conditions = self.service.filters.build_filter_sql(
                status=status,
                method=method,
                type_filter=type_filter,
                url=url,
                apply_groups=apply_groups,
                target=None,  # Don't filter by target in SQL
            )

        # Add state filter
        state_conditions = []
        if state:
            state_conditions.append(f"state = '{state}'")

        # Combine conditions
        all_conditions = []
        if conditions:
            all_conditions.append(conditions)
        if state_conditions:
            all_conditions.append(" AND ".join(state_conditions))

        if all_conditions:
            sql += f" WHERE {' AND '.join(all_conditions)}"

        sort_dir = "ASC" if order.lower() == "asc" else "DESC"
        sql += f" ORDER BY last_activity {sort_dir}"

        # Aggregate from all CDPSessions
        all_rows = aggregate_query(cdps, sql, error_context="query network")

        # Sort by last_activity (index 15) for proper cross-target ordering
        all_rows.sort(key=lambda r: r[15] or 0, reverse=(order.lower() == "desc"))
        all_rows = all_rows[:limit]

        # Convert to dicts
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
            "pause_stage",
            "paused_id",
            "frames_sent",
            "frames_received",
            "started_datetime",
            "last_activity",
            "target",
            "body_status",
        ]

        return [dict(zip(columns, row)) for row in all_rows]

    def get_request_details(self, row_id: int, target: str | None = None) -> dict | None:
        """Get HAR entry with proper nested structure.

        Args:
            row_id: Row ID from har_summary.
            target: Target ID - required to find the correct CDPSession

        Returns:
            HAR-structured dict or None if not found.

        Structure matches HAR spec:
            {
                "id": 123,
                "request": {"method", "url", "headers", "postData"},
                "response": {"status", "statusText", "headers", "content"},
                "time": 150,
                "state": "complete",
                "pause_stage": "Response",  # If paused
                ...
            }
        """
        if not self.service:
            return None

        cdp = self.service.resolve_cdp(row_id, "har_summary", target=target)
        if not cdp:
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
            pause_stage,
            paused_id,
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

        rows = cdp.query(sql, [row_id])
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
            "pause_stage",
            "paused_id",
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

        # Add pause info if paused
        if flat["pause_stage"]:
            har["pause_stage"] = flat["pause_stage"]

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

    def fetch_body(self, request_id: str, target: str | None = None) -> dict | None:
        """Fetch response body for a request.

        Args:
            request_id: CDP request ID.
            target: Target ID. If None, searches all connections.

        Returns:
            - {"body": str, "base64Encoded": bool} on success
            - {"error": str} if fetch failed
            - None if no service/connection available
        """
        if not self.service:
            return None

        if target:
            conn = self.service.connections.get(target)
            if not conn:
                return None
            return conn.cdp.fetch_body(request_id)
        else:
            # Search all connections for this request_id
            error_results = []
            for conn in self.service.connections.values():
                result = conn.cdp.fetch_body(request_id)
                if result and "error" not in result:
                    return result
                if result and "error" in result:
                    error_results.append(result)

            # All failed - return first error (preserve capture metadata)
            if error_results:
                return error_results[0]
            return None

    def fetch_websocket_frames(self, request_id: str, target: str | None = None) -> dict | None:
        """Fetch WebSocket frames for a request.

        Args:
            request_id: CDP request ID.
            target: Target ID. If None, searches all connections.

        Returns:
            Dict with 'sent' and 'received' lists of frames, or None.
            Each frame has: opcode, payloadData, mask, timestamp
        """
        if not self.service:
            return None

        sql = """
        SELECT
            method,
            json_extract_string(event, '$.params.timestamp') as timestamp,
            json_extract(event, '$.params.response') as frame
        FROM events
        WHERE method IN ('Network.webSocketFrameSent', 'Network.webSocketFrameReceived')
          AND request_id = ?
        ORDER BY timestamp ASC
        """

        def query_frames(cdp):
            rows = cdp.query(sql, [request_id])
            sent = []
            received = []
            for method, timestamp, frame_json in rows:
                frame = json.loads(frame_json) if isinstance(frame_json, str) else frame_json
                frame_data = {
                    "opcode": frame.get("opcode") if frame else None,
                    "payloadData": frame.get("payloadData") if frame else None,
                    "mask": frame.get("mask") if frame else None,
                    "timestamp": float(timestamp) if timestamp else None,
                }
                if method == "Network.webSocketFrameSent":
                    sent.append(frame_data)
                else:
                    received.append(frame_data)
            return {"sent": sent, "received": received}

        if target:
            conn = self.service.connections.get(target)
            if conn:
                return query_frames(conn.cdp)
            return None

        # Search all connections
        for conn in self.service.connections.values():
            try:
                result = query_frames(conn.cdp)
                if result["sent"] or result["received"]:
                    return result
            except Exception:
                pass
        return None

    def get_request_id(self, row_id: int, target: str | None = None) -> str | None:
        """Get CDP request_id for a row ID.

        Args:
            row_id: Row ID from har_summary.
            target: Target ID. If None, searches all connections.

        Returns:
            CDP request ID or None.
        """
        if not self.service:
            return None

        cdp = self.service.resolve_cdp(row_id, "har_summary", target=target)
        if not cdp:
            return None
        result = cdp.query("SELECT request_id FROM har_summary WHERE id = ?", [row_id])
        return result[0][0] if result else None

    def get_har_id_by_request_id(self, request_id: str, target: str | None = None) -> int | None:
        """Find HAR summary row ID by CDP request_id.

        Args:
            request_id: CDP request ID (from Network.responseReceived).
            target: Target ID. If None, searches all connections.

        Returns:
            HAR summary row ID or None if not found.
        """
        if not self.service:
            return None

        if target:
            conn = self.service.connections.get(target)
            if not conn:
                return None
            result = conn.cdp.query(
                "SELECT id FROM har_summary WHERE request_id = ? LIMIT 1",
                [request_id],
            )
            return result[0][0] if result else None
        else:
            for conn in self.service.connections.values():
                try:
                    result = conn.cdp.query(
                        "SELECT id FROM har_summary WHERE request_id = ? LIMIT 1",
                        [request_id],
                    )
                    if result:
                        return result[0][0]
                except Exception:
                    pass
            return None

    def _find_redirect_chain(
        self,
        request_id: str,
        request_url: str,
        target: str | None = None,
        max_hops: int = 5,
    ) -> list[tuple[str, int]]:
        """Find the redirect chain starting from a request.

        Walks the chain by finding Network.requestWillBeSent events where
        redirectResponse.url matches the current request's URL.

        Args:
            request_id: Starting request ID (the 3xx response)
            request_url: URL of the starting request
            target: Target ID for CDP session
            max_hops: Maximum redirects to follow (default 5)

        Returns:
            List of (request_id, har_row_id) tuples in chain order.
            First element is the original request, last is the final.
            Returns empty list if chain walking fails.
        """
        if not self.service:
            return []

        # Get CDPSession
        cdp = None
        if target:
            conn = self.service.connections.get(target)
            if conn:
                cdp = conn.cdp
        else:
            # Find connection with this request_id
            for conn in self.service.connections.values():
                result = conn.cdp.query(
                    "SELECT 1 FROM har_summary WHERE request_id = ? LIMIT 1",
                    [request_id],
                )
                if result:
                    cdp = conn.cdp
                    break

        if not cdp:
            return []

        # Get HAR row ID for starting request
        start_har_id = self.get_har_id_by_request_id(request_id, target)
        if start_har_id is None:
            return []

        chain: list[tuple[str, int]] = [(request_id, start_har_id)]
        seen_ids: set[str] = {request_id}
        current_url = request_url

        for _ in range(max_hops):
            # Find next request: look for requestWillBeSent where redirectResponse.url
            # matches current URL (meaning this request was triggered by redirecting from current)
            result = cdp.query(
                """
                SELECT
                    request_id as next_id
                FROM events
                WHERE method = 'Network.requestWillBeSent'
                  AND json_extract_string(event, '$.params.redirectResponse.url') = ?
                ORDER BY rowid ASC
                LIMIT 1
                """,
                [current_url],
            )

            if not result or not result[0][0]:
                # No more redirects - chain complete
                break

            next_id = result[0][0]

            # Check for loops
            if next_id in seen_ids:
                logger.warning(f"Redirect loop detected: {next_id} already in chain")
                break

            # Get HAR row ID and URL for next request
            next_har_id = self.get_har_id_by_request_id(next_id, target)
            if next_har_id is None:
                # Can't find HAR entry - chain broken
                break

            # Get URL of next request for continuing the chain
            url_result = cdp.query(
                "SELECT url FROM har_summary WHERE request_id = ? LIMIT 1",
                [next_id],
            )
            if not url_result:
                break

            chain.append((next_id, next_har_id))
            seen_ids.add(next_id)
            current_url = url_result[0][0]

        return chain

    def select_fields(self, har_entry: dict, patterns: list[str] | None) -> dict:
        """Apply ES-style field selection to HAR entry.

        Args:
            har_entry: Full HAR entry with nested structure.
            patterns: Field patterns or None for minimal.

        Patterns:
            - None: minimal default fields
            - ["*"]: all fields
            - ["request.*"]: all request fields
            - ["response.content"]: fetch response body on-demand

        Returns:
            HAR entry with only selected fields.
        """
        minimal_fields = ["request.method", "request.url", "response.status", "time", "state"]

        if patterns is None:
            result: dict = {}
            for field in minimal_fields:
                parts = field.split(".")
                value = get_nested(har_entry, parts, case_insensitive=True)
                if value is not None:
                    set_nested(result, parts, value)
            return result

        if patterns == ["*"] or "*" in patterns:
            return har_entry

        result = {}
        for pattern in patterns:
            if pattern == "*":
                return har_entry

            # Special: response.content triggers body fetch
            if pattern == "response.content" or pattern.startswith("response.content."):
                self._fetch_response_content(har_entry, result)
                continue

            # Special: websocket.frames triggers frame fetch
            if pattern == "websocket.frames" or pattern.startswith("websocket.frames."):
                self._fetch_websocket_frames_for_entry(har_entry, result)
                continue

            # Standard field selection
            parts = pattern.split(".")
            if pattern.endswith(".*"):
                prefix_parts = pattern[:-2].split(".")
                value = get_nested(har_entry, prefix_parts, case_insensitive=True)
                if value is not None:
                    set_nested(result, prefix_parts, value)
            else:
                value = get_nested(har_entry, parts, case_insensitive=True)
                if value is not None:
                    set_nested(result, parts, value)

        return result

    def _fetch_response_content(self, har_entry: dict, result: dict) -> None:
        """Fetch response body and add to result dict."""
        request_id = har_entry.get("request_id")
        if not request_id:
            return

        status = har_entry.get("response", {}).get("status", 0)
        request_url = har_entry.get("request", {}).get("url", "")
        chain_ids: list[int] | None = None
        fetch_id = request_id

        # For 3xx redirects, find chain and fetch from final
        if 300 <= status < 400 and request_url:
            chain_result = self._find_redirect_chain(request_id, request_url)
            if chain_result and len(chain_result) > 1:
                chain_ids = [har_id for _, har_id in chain_result]
                fetch_id = chain_result[-1][0]

        body_result = self.fetch_body(fetch_id)

        content = har_entry.get("response", {}).get("content", {}).copy()
        if body_result and "error" not in body_result:
            content["text"] = body_result.get("body")
            content["encoding"] = "base64" if body_result.get("base64Encoded") else None
        elif body_result and "error" in body_result:
            content["text"] = None
            content["error"] = body_result["error"]
        else:
            content["text"] = None

        # Include capture metadata if present (timing diagnostics)
        if body_result and "capture" in body_result:
            content["capture"] = body_result["capture"]

        if chain_ids:
            content["chain"] = chain_ids

        set_nested(result, ["response", "content"], content)

    def _fetch_websocket_frames_for_entry(self, har_entry: dict, result: dict) -> None:
        """Fetch WebSocket frames and add to result dict."""
        if har_entry.get("protocol") != "websocket":
            return

        request_id = har_entry.get("request_id")
        if not request_id:
            return

        frames_result = self.fetch_websocket_frames(request_id)
        websocket_data = result.get("websocket", {})
        websocket_data["frames"] = frames_result or {"sent": [], "received": []}
        result["websocket"] = websocket_data


__all__ = ["NetworkService"]
