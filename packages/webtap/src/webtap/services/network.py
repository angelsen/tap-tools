"""Network monitoring service using HAR views.

PUBLIC API:
  - NetworkService: Network event queries using HAR views
"""

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class NetworkService:
    """Network event queries using HAR views."""

    def __init__(self):
        """Initialize network service."""
        self.service: "Any" = None  # WebTapService reference

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
            target
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
        all_rows = []
        for cdp in cdps:
            try:
                rows = cdp.query(sql)
                all_rows.extend(rows)
            except Exception as e:
                logger.warning(f"Failed to query network from {cdp.target}: {e}")

        # Sort by last_activity (index 15) for proper cross-target ordering
        all_rows.sort(key=lambda r: r[15] or "", reverse=(order.lower() == "desc"))
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
            Dict with 'body' and 'base64Encoded' keys, or None.
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
            for conn in self.service.connections.values():
                try:
                    result = conn.cdp.fetch_body(request_id)
                    if result:
                        return result
                except Exception:
                    pass
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
          AND json_extract_string(event, '$.params.requestId') = ?
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

    def get_request_by_row_id(self, row_id: int, target: str | None = None) -> str | None:
        """Get request_id for a row ID.

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

    def get_request_id(self, row_id: int, target: str | None = None) -> str | None:
        """Get CDP request_id for a row ID.

        Args:
            row_id: Row ID from network table.
            target: Target ID - required to find the correct CDPSession

        Returns:
            CDP request ID or None.
        """
        return self.get_request_by_row_id(row_id, target)

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

    def select_fields(self, har_entry: dict, patterns: list[str] | None) -> dict:
        """Apply ES-style field selection to HAR entry.

        Args:
            har_entry: Full HAR entry with nested structure.
            patterns: Field patterns or None for minimal.

        Patterns:
            - None: minimal default fields
            - ["*"]: all fields
            - ["request.*"]: all request fields
            - ["request.headers.*"]: all request headers
            - ["request.headers.content-type"]: specific header
            - ["response.content"]: fetch response body on-demand

        Returns:
            HAR entry with only selected fields.
        """
        # Minimal fields for default view
        minimal_fields = ["request.method", "request.url", "response.status", "time", "state"]

        if patterns is None:
            # Minimal default - extract specific paths
            result: dict = {}
            for pattern in minimal_fields:
                parts = pattern.split(".")
                value = _get_nested(har_entry, parts)
                if value is not None:
                    _set_nested(result, parts, value)
            return result

        if patterns == ["*"]:
            return har_entry

        result = {}
        for pattern in patterns:
            if pattern == "*":
                return har_entry

            parts = pattern.split(".")

            # Special case: response.content triggers body fetch
            if pattern == "response.content" or pattern.startswith("response.content."):
                request_id = har_entry.get("request_id")
                if request_id:
                    body_result = self.fetch_body(request_id)
                    if body_result:
                        content = har_entry.get("response", {}).get("content", {}).copy()
                        content["text"] = body_result.get("body")
                        content["encoding"] = "base64" if body_result.get("base64Encoded") else None
                        _set_nested(result, ["response", "content"], content)
                    else:
                        _set_nested(result, ["response", "content"], {"text": None})
                continue

            # Special case: websocket.frames triggers frame fetch
            if pattern == "websocket.frames" or pattern.startswith("websocket.frames."):
                # Only fetch frames for WebSocket connections
                if har_entry.get("protocol") == "websocket":
                    request_id = har_entry.get("request_id")
                    if request_id:
                        frames_result = self.fetch_websocket_frames(request_id)
                        if frames_result:
                            websocket_data = result.get("websocket", {})
                            websocket_data["frames"] = frames_result
                            result["websocket"] = websocket_data
                        else:
                            websocket_data = result.get("websocket", {})
                            websocket_data["frames"] = {"sent": [], "received": []}
                            result["websocket"] = websocket_data
                continue

            # Wildcard: "request.headers.*" -> get all under that path
            if pattern.endswith(".*"):
                prefix = pattern[:-2]
                prefix_parts = prefix.split(".")
                obj = _get_nested(har_entry, prefix_parts)
                if obj is not None:
                    _set_nested(result, prefix_parts, obj)
            else:
                # Specific path
                value = _get_nested(har_entry, parts)
                if value is not None:
                    _set_nested(result, parts, value)

        return result


def _get_nested(obj: dict | None, path: list[str]):
    """Get nested value by path, case-insensitive for headers."""
    for key in path:
        if obj is None:
            return None
        if isinstance(obj, dict):
            # Case-insensitive lookup
            matching_key = next((k for k in obj.keys() if k.lower() == key.lower()), None)
            if matching_key:
                obj = obj.get(matching_key)
            else:
                return None
        else:
            return None
    return obj


def _set_nested(result: dict, path: list[str], value) -> None:
    """Set nested value by path, creating intermediate dicts."""
    current = result
    for key in path[:-1]:
        if key not in current:
            current[key] = {}
        current = current[key]
    current[path[-1]] = value


__all__ = ["NetworkService"]
