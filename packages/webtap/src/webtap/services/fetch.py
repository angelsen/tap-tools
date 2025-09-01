"""Fetch interception service for request/response debugging.

Dead simple: When enabled, all requests pause. User inspects, modifies, continues.
All events stored in DuckDB - no caching or tracking needed.
"""

import json
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from webtap.cdp import CDPSession
    from webtap.services.body import BodyService

logger = logging.getLogger(__name__)


class FetchService:
    """Manages fetch interception for debugging HTTP traffic."""

    def __init__(self):
        """Initialize fetch service."""
        self.enabled = False
        self.cdp: CDPSession | None = None  # Set when enabled
        self.body_service: BodyService | None = None  # Optional dependency for cache clearing

    @property
    def paused_count(self) -> int:
        """Count of currently paused requests (latest stage only per fetch_id)."""
        if not self.cdp:
            return 0
        # Count unique fetch_ids (not total events)
        result = self.cdp.query("""
            SELECT COUNT(DISTINCT json_extract_string(event, '$.params.requestId'))
            FROM events 
            WHERE json_extract_string(event, '$.method') = 'Fetch.requestPaused'
        """)
        return result[0][0] if result else 0

    def get_paused_rowids(self) -> list[int]:
        """Get all paused request rowids (latest stage only per fetch_id).

        Returns:
            List of rowids for paused requests
        """
        if not self.cdp:
            return []
        # Only get the latest stage for each fetch_id
        results = self.cdp.query("""
            WITH latest_stage AS (
                SELECT 
                    MAX(rowid) as rowid,
                    json_extract_string(event, '$.params.requestId') as fetch_id
                FROM events 
                WHERE json_extract_string(event, '$.method') = 'Fetch.requestPaused'
                GROUP BY fetch_id
            )
            SELECT rowid FROM latest_stage ORDER BY rowid DESC
        """)
        return [row[0] for row in results]

    def _get_paused_event(self, rowid: int) -> dict | None:
        """Get a specific paused request event by rowid (internal use)."""
        if not self.cdp:
            return None
        result = self.cdp.query(
            "SELECT event FROM events WHERE rowid = ? AND json_extract_string(event, '$.method') = 'Fetch.requestPaused'",
            [rowid],
        )
        if result:
            return json.loads(result[0][0])
        return None

    def enable(self, cdp) -> dict:
        """Enable fetch interception - all requests will pause.

        Args:
            cdp: CDP session for executing commands

        Returns:
            Status dict
        """
        if self.enabled:
            return {"enabled": True, "message": "Already enabled"}

        self.cdp = cdp

        try:
            # Enable Fetch domain - intercept everything
            cdp.execute(
                "Fetch.enable",
                {
                    "patterns": [
                        {"urlPattern": "*", "requestStage": "Request"},
                        {"urlPattern": "*", "requestStage": "Response"},
                    ]
                },
            )

            self.enabled = True
            logger.info("Fetch interception enabled")

            return {"enabled": True, "paused": self.paused_count}

        except Exception as e:
            logger.error(f"Failed to enable fetch: {e}")
            return {"enabled": False, "error": str(e)}

    def disable(self) -> dict:
        """Disable fetch interception and continue all paused requests.

        Returns:
            Status dict
        """
        if not self.enabled:
            return {"enabled": False, "message": "Already disabled"}

        if not self.cdp:
            return {"enabled": False, "error": "No CDP session"}

        try:
            # Get all paused requests from DB
            paused_rowids = self.get_paused_rowids()

            # Continue all paused requests
            continued = 0
            for rowid in paused_rowids:
                try:
                    event_data = self._get_paused_event(rowid)
                    if not event_data:
                        continue

                    params = event_data.get("params", {})
                    request_id = params.get("requestId")

                    if request_id:
                        # Check if this is response stage
                        if "responseStatusCode" in params:
                            self.cdp.execute("Fetch.continueResponse", {"requestId": request_id})
                        else:
                            self.cdp.execute("Fetch.continueRequest", {"requestId": request_id})
                        continued += 1
                except Exception as e:
                    logger.error(f"Failed to continue request: {e}")

            # Disable Fetch domain
            self.cdp.execute("Fetch.disable")

            self.enabled = False

            # Clear body cache when fetch is disabled
            if self.body_service:
                self.body_service.clear_cache()

            logger.info(f"Fetch interception disabled, continued {continued} requests")
            return {"enabled": False, "continued": continued}

        except Exception as e:
            logger.error(f"Failed to disable fetch: {e}")
            return {"enabled": self.enabled, "error": str(e)}

    def get_paused_list(self) -> list[dict]:
        """Get list of paused requests for display.

        Returns:
            List of request summaries (only latest stage per fetch_id)
        """
        if not self.cdp:
            return []

        # Simple query: Show only the latest fetch_id per networkId
        # When redirects happen, new fetch_ids are created with the same networkId
        # By showing only the latest, we automatically hide completed requests
        results = self.cdp.query("""
            WITH latest_per_network AS (
                SELECT 
                    MAX(rowid) as max_rowid,
                    json_extract_string(event, '$.params.networkId') as network_id
                FROM events 
                WHERE json_extract_string(event, '$.method') = 'Fetch.requestPaused'
                GROUP BY network_id
            )
            SELECT 
                e.rowid,
                json_extract_string(e.event, '$.params.request.url') as url,
                json_extract_string(e.event, '$.params.request.method') as method,
                json_extract_string(e.event, '$.params.responseStatusCode') as status
            FROM events e
            INNER JOIN latest_per_network l ON e.rowid = l.max_rowid
            ORDER BY e.rowid DESC
        """)

        rows = []
        for row in results:
            rowid, url, method, status = row

            # Determine stage based on status
            stage = "Response" if status else "Request"

            rows.append(
                {
                    "ID": str(rowid),
                    "Stage": stage,
                    "Method": method or "GET",
                    "Status": status or "-",
                    "URL": url[:60] if url else "-",
                }
            )

        return rows

    def continue_request(self, rowid: int, modifications: dict | None = None, wait: float = 0.5) -> dict:
        """Continue a paused request with optional modifications.

        Args:
            rowid: Row ID from requests() table
            modifications: Direct CDP parameters to pass
            wait: Seconds to wait for follow-up requests (0 to disable)

        Returns:
            Status dict with any follow-up requests detected
        """
        if not self.enabled or not self.cdp:
            return {"error": "Fetch not enabled"}

        # Get event from DB
        event_data = self._get_paused_event(rowid)

        if not event_data:
            return {"error": f"Paused request with rowid {rowid} not found"}

        try:
            params = event_data.get("params", {})
            request_id = params.get("requestId")
            network_id = params.get("networkId")  # Extract for tracking

            if not request_id:
                return {"error": "No requestId in event"}

            # Check if this is response stage
            if "responseStatusCode" in params:
                # Continue response
                cdp_params = {"requestId": request_id}
                if modifications:
                    # Response modifications (responseCode, responseHeaders, etc.)
                    cdp_params.update(modifications)

                self.cdp.execute("Fetch.continueResponse", cdp_params)
                stage = "response"
            else:
                # Continue request
                cdp_params = {"requestId": request_id}
                if modifications:
                    # Request modifications (url, method, headers, postData)
                    cdp_params.update(modifications)

                self.cdp.execute("Fetch.continueRequest", cdp_params)
                stage = "request"

            # Wait for follow-up if requested
            follow_up = None
            if wait > 0 and network_id:
                import time

                start_time = time.time()

                while time.time() - start_time < wait:
                    # Check for new request with same networkId
                    new_events = self.cdp.query(
                        """
                        SELECT rowid,
                               json_extract_string(event, '$.params.request.url') as url,
                               json_extract_string(event, '$.params.responseStatusCode') as status
                        FROM events 
                        WHERE json_extract_string(event, '$.method') = 'Fetch.requestPaused'
                          AND json_extract_string(event, '$.params.networkId') = ?
                          AND rowid > ?
                        ORDER BY rowid ASC
                        LIMIT 1
                    """,
                        [network_id, rowid],
                    )

                    if new_events:
                        new_rowid, url, status = new_events[0]
                        follow_up = {"rowid": new_rowid, "url": url[:60] if url else None, "status": status}
                        break

                    time.sleep(0.05)  # 50ms polling interval

            # Build response
            result = {"continued": rowid, "stage": stage, "remaining": self.paused_count}

            if follow_up:
                result["follow_up"] = follow_up

            return result

        except Exception as e:
            logger.error(f"Failed to continue rowid {rowid}: {e}")
            return {"error": str(e)}

    def fail_request(self, rowid: int, reason: str = "BlockedByClient") -> dict:
        """Fail a paused request.

        Args:
            rowid: Row ID from requests() table
            reason: CDP error reason

        Returns:
            Status dict
        """
        if not self.enabled or not self.cdp:
            return {"error": "Fetch not enabled"}

        # Get event from DB
        event_data = self._get_paused_event(rowid)

        if not event_data:
            return {"error": f"Paused request with rowid {rowid} not found"}

        try:
            params = event_data.get("params", {})
            request_id = params.get("requestId")

            if not request_id:
                return {"error": "No requestId in event"}

            self.cdp.execute("Fetch.failRequest", {"requestId": request_id, "errorReason": reason})

            # Count remaining paused
            count = self.paused_count - 1  # Minus the one we just failed

            return {
                "failed": rowid,
                "reason": reason,
                "remaining": max(0, count),  # Ensure non-negative
            }

        except Exception as e:
            logger.error(f"Failed to fail rowid {rowid}: {e}")
            return {"error": str(e)}

    def continue_all(self) -> dict:
        """Continue all paused requests without modifications.

        Returns:
            Status dict
        """
        if not self.enabled or not self.cdp:
            return {"error": "Fetch not enabled"}

        # Get all paused requests
        paused_rowids = self.get_paused_rowids()

        count = len(paused_rowids)
        errors = []

        for rowid in paused_rowids:
            result = self.continue_request(rowid)
            if "error" in result:
                errors.append(f"{rowid}: {result['error']}")

        return {"continued": count - len(errors), "errors": errors if errors else None}

    def fail_all(self, reason: str = "BlockedByClient") -> dict:
        """Fail all paused requests.

        Args:
            reason: CDP error reason

        Returns:
            Status dict
        """
        if not self.enabled or not self.cdp:
            return {"error": "Fetch not enabled"}

        # Get all paused requests
        paused_rowids = self.get_paused_rowids()

        count = len(paused_rowids)
        errors = []

        for rowid in paused_rowids:
            result = self.fail_request(rowid, reason)
            if "error" in result:
                errors.append(f"{rowid}: {result['error']}")

        return {"failed": count - len(errors), "errors": errors if errors else None}
