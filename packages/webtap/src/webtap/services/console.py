"""Console monitoring service for browser messages."""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from webtap.cdp import CDPSession

logger = logging.getLogger(__name__)


class ConsoleService:
    """Console event queries and monitoring."""

    def __init__(self):
        """Initialize console service."""
        self.cdp: CDPSession | None = None

    @property
    def message_count(self) -> int:
        """Count of all console messages."""
        if not self.cdp:
            return 0
        result = self.cdp.query(
            "SELECT COUNT(*) FROM events WHERE json_extract_string(event, '$.method') IN ('Runtime.consoleAPICalled', 'Log.entryAdded')"
        )
        return result[0][0] if result else 0

    @property
    def error_count(self) -> int:
        """Count of console errors."""
        if not self.cdp:
            return 0
        result = self.cdp.query("""
            SELECT COUNT(*) FROM events 
            WHERE json_extract_string(event, '$.method') IN ('Runtime.consoleAPICalled', 'Log.entryAdded')
            AND (
                json_extract_string(event, '$.params.type') = 'error' 
                OR json_extract_string(event, '$.params.entry.level') = 'error'
            )
        """)
        return result[0][0] if result else 0

    def get_recent_messages(self, limit: int = 50, level: str | None = None) -> list[tuple]:
        """Get recent console messages with common fields extracted.

        Args:
            limit: Maximum results
            level: Optional filter by level (error, warning, log, info)
        """
        if not self.cdp:
            return []

        sql = """
        SELECT 
            rowid,
            COALESCE(
                json_extract_string(event, '$.params.type'),
                json_extract_string(event, '$.params.entry.level')
            ) as Level,
            COALESCE(
                json_extract_string(event, '$.params.source'),
                json_extract_string(event, '$.params.entry.source'),
                'console'
            ) as Source,
            COALESCE(
                json_extract_string(event, '$.params.args[0].value'),
                json_extract_string(event, '$.params.entry.text')
            ) as Message,
            COALESCE(
                json_extract_string(event, '$.params.timestamp'),
                json_extract_string(event, '$.params.entry.timestamp')
            ) as Time
        FROM events 
        WHERE json_extract_string(event, '$.method') IN ('Runtime.consoleAPICalled', 'Log.entryAdded')
        """

        if level:
            sql += f"""
            AND (
                json_extract_string(event, '$.params.type') = '{level.lower()}'
                OR json_extract_string(event, '$.params.entry.level') = '{level.lower()}'
            )
            """

        sql += f" ORDER BY rowid DESC LIMIT {limit}"

        return self.cdp.query(sql)

    def get_errors(self, limit: int = 20) -> list[tuple]:
        """Get console errors only.

        Args:
            limit: Maximum results
        """
        return self.get_recent_messages(limit=limit, level="error")

    def get_warnings(self, limit: int = 20) -> list[tuple]:
        """Get console warnings only.

        Args:
            limit: Maximum results
        """
        return self.get_recent_messages(limit=limit, level="warning")

    def clear_browser_console(self) -> bool:
        """Clear console in the browser (CDP command)."""
        if not self.cdp:
            return False

        try:
            self.cdp.execute("Runtime.discardConsoleEntries")
            return True
        except Exception as e:
            logger.error(f"Failed to clear browser console: {e}")
            return False
