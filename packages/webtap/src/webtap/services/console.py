"""Console monitoring service for browser messages.

PUBLIC API:
  - ConsoleService: Console event queries and monitoring
"""

import logging
from typing import Any

from webtap.services._utils import aggregate_query

logger = logging.getLogger(__name__)


class ConsoleService:
    """Console event queries and monitoring.

    Provides access to browser console messages captured via CDP.
    Supports filtering by level (error, warning, log, info) and
    querying message counts.

    Attributes:
        service: WebTapService reference for aggregation
    """

    def __init__(self):
        """Initialize console service."""
        self.service: "Any" = None  # WebTapService reference

    def set_service(self, service: "Any") -> None:
        """Set service reference.

        Args:
            service: WebTapService instance
        """
        self.service = service

    @property
    def message_count(self) -> int:
        """Count of all console messages across all connections."""
        if not self.service:
            return 0
        total = 0
        for conn in self.service.connections.values():
            try:
                result = conn.cdp.query(
                    "SELECT COUNT(*) FROM events WHERE method IN ('Runtime.consoleAPICalled', 'Log.entryAdded')"
                )
                total += result[0][0] if result else 0
            except Exception:
                pass
        return total

    @property
    def error_count(self) -> int:
        """Count of console errors across all connections."""
        if not self.service:
            return 0
        total = 0
        for conn in self.service.connections.values():
            try:
                result = conn.cdp.query("""
                    SELECT COUNT(*) FROM events
                    WHERE method IN ('Runtime.consoleAPICalled', 'Log.entryAdded')
                    AND (
                        json_extract_string(event, '$.params.type') = 'error'
                        OR json_extract_string(event, '$.params.entry.level') = 'error'
                    )
                """)
                total += result[0][0] if result else 0
            except Exception:
                pass
        return total

    def get_recent_messages(
        self,
        targets: list[str] | None = None,
        limit: int = 50,
        level: str | None = None,
        target: str | list[str] | None = None,
    ) -> list[tuple]:
        """Get recent console messages with common fields extracted.

        Args:
            targets: Explicit target list, or None for tracked/all
            limit: Maximum results
            level: Optional filter by level (error, warning, log, info)
            target: Legacy parameter - use targets instead
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
            ) as Time,
            target
        FROM events
        WHERE method IN ('Runtime.consoleAPICalled', 'Log.entryAdded')
        """

        if level:
            sql += f"""
            AND (
                json_extract_string(event, '$.params.type') = '{level.lower()}'
                OR json_extract_string(event, '$.params.entry.level') = '{level.lower()}'
            )
            """

        sql += " ORDER BY rowid DESC"

        # Aggregate from all CDPSessions
        all_rows = aggregate_query(cdps, sql, error_context="query console")

        # Sort by timestamp (index 4) for proper cross-target ordering
        all_rows.sort(key=lambda r: r[4] or "", reverse=True)
        return all_rows[:limit]

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

    def clear_browser_console(self, targets: list[str] | None = None) -> bool:
        """Clear console in the browser (CDP command) for all or specified targets.

        Args:
            targets: Explicit target list, or None for tracked/all

        Returns:
            True if all succeeded, False if any failed
        """
        if not self.service:
            return False

        cdps = self.service.get_cdps(targets)
        if not cdps:
            return False

        success = True
        for cdp in cdps:
            try:
                cdp.execute("Runtime.discardConsoleEntries")
            except Exception as e:
                logger.error(f"Failed to clear browser console on {cdp.target}: {e}")
                success = False

        return success

    def get_entry_details(self, row_id: int, target: str | None = None) -> dict | None:
        """Get full console entry by database row ID.

        Args:
            row_id: Database rowid from events table
            target: Target ID - required to find the correct CDPSession

        Returns:
            Normalized console entry dict or None if not found
        """
        import json

        if not self.service:
            return None

        cdp = self.service.resolve_cdp(row_id, "events", id_column="rowid", target=target)
        if not cdp:
            return None

        sql = "SELECT event FROM events WHERE rowid = ?"
        rows = cdp.query(sql, [row_id])
        if not rows:
            return None

        event = json.loads(rows[0][0])
        params = event.get("params", {})

        # Normalize both Runtime.consoleAPICalled and Log.entryAdded
        if event.get("method") == "Log.entryAdded":
            entry = params.get("entry", {})
            return {
                "id": row_id,
                "method": event["method"],
                "type": entry.get("level"),
                "source": entry.get("source"),
                "message": entry.get("text"),
                "timestamp": entry.get("timestamp"),
                "entry": entry,
                "stackTrace": entry.get("stackTrace"),
            }
        else:  # Runtime.consoleAPICalled
            return {
                "id": row_id,
                "method": event.get("method"),
                "type": params.get("type"),
                "source": "console",
                "message": self._extract_message(params.get("args", [])),
                "timestamp": params.get("timestamp"),
                "args": params.get("args"),
                "stackTrace": params.get("stackTrace"),
                "executionContextId": params.get("executionContextId"),
            }

    def select_fields(self, entry: dict, patterns: list[str] | None) -> dict:
        """Apply field selection patterns to console entry.

        Args:
            entry: Full console entry dict
            patterns: Field patterns (None for minimal, ["*"] for all)

        Returns:
            Entry with only selected fields
        """
        if patterns is None:
            return {k: entry.get(k) for k in ["type", "message", "source", "timestamp"] if entry.get(k) is not None}
        if "*" in patterns:
            return entry
        return {k: entry.get(k) for k in patterns if entry.get(k) is not None}

    def _extract_message(self, args: list) -> str:
        """Extract message from console args."""
        if not args:
            return ""
        first = args[0]
        return first.get("value") or first.get("description") or str(first)


__all__ = ["ConsoleService"]
