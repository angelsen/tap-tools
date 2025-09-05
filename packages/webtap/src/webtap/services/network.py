"""Network monitoring service for request/response tracking."""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from webtap.cdp import CDPSession

logger = logging.getLogger(__name__)


class NetworkService:
    """Network event queries and monitoring."""

    def __init__(self):
        """Initialize network service."""
        self.cdp: CDPSession | None = None

    @property
    def request_count(self) -> int:
        """Count of all network requests."""
        if not self.cdp:
            return 0
        result = self.cdp.query(
            "SELECT COUNT(*) FROM events WHERE json_extract_string(event, '$.method') = 'Network.responseReceived'"
        )
        return result[0][0] if result else 0

    def get_recent_requests(self, limit: int = 20, filter_sql: str = "") -> list[tuple]:
        """Get recent network requests with common fields extracted.

        Args:
            limit: Maximum results
            filter_sql: Optional filter SQL to append
        """
        if not self.cdp:
            return []

        sql = """
        SELECT 
            rowid,
            json_extract_string(event, '$.params.requestId') as RequestId,
            COALESCE(
                json_extract_string(event, '$.params.request.method'),
                json_extract_string(event, '$.params.response.request.method'),
                'GET'
            ) as Method,
            json_extract_string(event, '$.params.response.status') as Status,
            COALESCE(
                json_extract_string(event, '$.params.response.url'),
                json_extract_string(event, '$.params.request.url')
            ) as URL,
            json_extract_string(event, '$.params.type') as Type,
            json_extract_string(event, '$.params.response.encodedDataLength') as Size
        FROM events 
        WHERE json_extract_string(event, '$.method') = 'Network.responseReceived'
        """

        if filter_sql:
            sql += " AND " + filter_sql

        sql += f" ORDER BY rowid DESC LIMIT {limit}"

        return self.cdp.query(sql)

    def get_failed_requests(self, limit: int = 20) -> list[tuple]:
        """Get failed network requests (4xx, 5xx status codes).

        Args:
            limit: Maximum results
        """
        if not self.cdp:
            return []

        sql = f"""
        SELECT 
            rowid,
            json_extract_string(event, '$.params.requestId') as RequestId,
            json_extract_string(event, '$.params.response.status') as Status,
            json_extract_string(event, '$.params.response.url') as URL,
            json_extract_string(event, '$.params.response.statusText') as StatusText
        FROM events 
        WHERE json_extract_string(event, '$.method') = 'Network.responseReceived'
        AND json_extract_string(event, '$.params.response.status') >= '400'
        ORDER BY rowid DESC LIMIT {limit}
        """

        return self.cdp.query(sql)

    def get_request_by_id(self, request_id: str) -> list[dict]:
        """Get all events for a specific request ID.

        Args:
            request_id: CDP request ID
        """
        if not self.cdp:
            return []

        results = self.cdp.query(
            "SELECT event FROM events WHERE json_extract_string(event, '$.params.requestId') = ?", [request_id]
        )

        import json

        return [json.loads(row[0]) for row in results] if results else []
