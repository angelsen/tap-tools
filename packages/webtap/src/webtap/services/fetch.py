"""Fetch interception service for request/response debugging."""

import json
import logging
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from webtap.cdp import CDPSession
    from webtap.services.body import BodyService

logger = logging.getLogger(__name__)


class FetchService:
    """Fetch interception with explicit actions."""

    def __init__(self):
        """Initialize fetch service."""
        self.enabled = False
        self.enable_response_stage = False  # Config option for future
        self.cdp: CDPSession | None = None
        self.body_service: BodyService | None = None
        self._broadcast_callback: "Any | None" = None  # Callback to service._trigger_broadcast()

    def set_broadcast_callback(self, callback: "Any") -> None:
        """Set callback for broadcasting state changes.

        Args:
            callback: Function to call when state changes (service._trigger_broadcast)
        """
        self._broadcast_callback = callback

    def _trigger_broadcast(self) -> None:
        """Trigger SSE broadcast via service callback (ensures snapshot update)."""
        if self._broadcast_callback:
            try:
                self._broadcast_callback()
            except Exception as e:
                logger.debug(f"Failed to trigger broadcast: {e}")

    # ============= Core State Queries =============

    def get_paused_list(self) -> list[dict[str, Any]]:
        """Get list of currently paused requests for display.

        Returns:
            List with ID, Stage, Method, Status, URL for each paused request
        """
        if not self.cdp:
            return []

        results = self.cdp.query(
            """
            WITH fetch_events AS (
                SELECT 
                    rowid,
                    json_extract_string(event, '$.params.requestId') as request_id,
                    json_extract_string(event, '$.params.networkId') as network_id,
                    json_extract_string(event, '$.params.responseStatusCode') as response_status,
                    json_extract_string(event, '$.params.request.url') as url,
                    json_extract_string(event, '$.params.request.method') as method,
                    CASE WHEN json_extract_string(event, '$.params.responseStatusCode') IS NOT NULL 
                         THEN 'Response' ELSE 'Request' END as stage
                FROM events
                WHERE json_extract_string(event, '$.method') = 'Fetch.requestPaused'
            ),
            completed_networks AS (
                SELECT DISTINCT json_extract_string(event, '$.params.requestId') as network_id
                FROM events
                WHERE json_extract_string(event, '$.method') = 'Network.loadingFinished'
            ),
            latest_per_request AS (
                SELECT request_id, MAX(rowid) as max_rowid
                FROM fetch_events
                GROUP BY request_id
            )
            SELECT 
                f.rowid,
                f.stage,
                f.method,
                f.response_status,
                f.url,
                f.network_id,
                f.request_id
            FROM fetch_events f
            INNER JOIN latest_per_request l ON f.rowid = l.max_rowid
            WHERE f.network_id NOT IN (SELECT network_id FROM completed_networks)
            ORDER BY f.rowid DESC
        """
        )

        return [
            {
                "ID": row[0],
                "Stage": row[1],
                "Method": row[2] or "GET",
                "Status": row[3] or "-",
                "URL": row[4][:60] if row[4] else "-",
                "_network_id": row[5],
                "_request_id": row[6],
            }
            for row in results
        ]

    @property
    def paused_count(self) -> int:
        """Count of actually paused requests (not completed)."""
        return len(self.get_paused_list())

    def get_paused_event(self, rowid: int) -> dict | None:
        """Get full event data for a paused request.

        Args:
            rowid: Row ID from the database

        Returns:
            Full CDP event data or None if not found
        """
        if not self.cdp:
            return None

        result = self.cdp.query(
            """
            SELECT event 
            FROM events 
            WHERE rowid = ? 
              AND json_extract_string(event, '$.method') = 'Fetch.requestPaused'
        """,
            [rowid],
        )

        if result:
            return json.loads(result[0][0])
        return None

    # ============= Enable/Disable =============

    def enable(self, cdp: "CDPSession", response_stage: bool = False) -> dict[str, Any]:
        """Enable fetch interception.

        Args:
            cdp: CDP session for executing commands
            response_stage: Whether to also pause at Response stage

        Returns:
            Status dict with enabled state and paused count
        """
        if self.enabled:
            return {"enabled": True, "message": "Already enabled"}

        self.cdp = cdp
        self.enable_response_stage = response_stage

        try:
            patterns = [{"urlPattern": "*", "requestStage": "Request"}]

            if response_stage:
                patterns.append({"urlPattern": "*", "requestStage": "Response"})

            cdp.execute("Fetch.enable", {"patterns": patterns})

            self.enabled = True
            stage_msg = "Request and Response stages" if response_stage else "Request stage only"
            logger.info(f"Fetch interception enabled ({stage_msg})")

            self._trigger_broadcast()  # Update snapshot
            return {"enabled": True, "stages": stage_msg, "paused": self.paused_count}

        except Exception as e:
            logger.error(f"Failed to enable fetch: {e}")
            return {"enabled": False, "error": str(e)}

    def disable(self) -> dict[str, Any]:
        """Disable fetch interception.

        Returns:
            Status dict with disabled state
        """
        if not self.enabled:
            return {"enabled": False, "message": "Already disabled"}

        if not self.cdp:
            return {"enabled": False, "error": "No CDP session"}

        try:
            self.cdp.execute("Fetch.disable")
            self.enabled = False

            # Clear body cache when fetch is disabled
            if self.body_service:
                self.body_service.clear_cache()

            logger.info("Fetch interception disabled")
            self._trigger_broadcast()  # Update snapshot
            return {"enabled": False}

        except Exception as e:
            logger.error(f"Failed to disable fetch: {e}")
            return {"enabled": self.enabled, "error": str(e)}

    # ============= Explicit Actions =============

    def continue_request(
        self, rowid: int, modifications: dict[str, Any] | None = None, wait_for_next: float = 0.5
    ) -> dict[str, Any]:
        """Continue a specific paused request.

        Args:
            rowid: Row ID from requests() table
            modifications: Optional modifications to apply
            wait_for_next: Time to wait for follow-up events (0 to disable)

        Returns:
            Dict with continuation status and optional next event info
        """
        if not self.enabled or not self.cdp:
            return {"error": "Fetch not enabled"}

        # Get the event
        event = self.get_paused_event(rowid)
        if not event:
            return {"error": f"Event {rowid} not found"}

        params = event["params"]
        request_id = params["requestId"]
        network_id = params.get("networkId")

        # Determine stage and continue
        if params.get("responseStatusCode"):
            # Response stage
            cdp_params = {"requestId": request_id}
            if modifications:
                cdp_params.update(modifications)
            self.cdp.execute("Fetch.continueResponse", cdp_params)
            stage = "response"
        else:
            # Request stage
            cdp_params = {"requestId": request_id}
            if modifications:
                cdp_params.update(modifications)
            self.cdp.execute("Fetch.continueRequest", cdp_params)
            stage = "request"

        result = {"continued": rowid, "stage": stage, "request_id": request_id}

        # Wait for follow-up if requested
        if wait_for_next > 0 and network_id:
            next_event = self._wait_for_next_event(request_id, network_id, rowid, wait_for_next)
            if next_event:
                result["next_event"] = next_event

        # Add remaining count
        result["remaining"] = self.paused_count

        return result

    def _wait_for_next_event(
        self, request_id: str, network_id: str, after_rowid: int, timeout: float
    ) -> dict[str, Any] | None:
        """Wait for the next event in the chain (response stage or redirect).

        Args:
            request_id: The request ID that was just continued
            network_id: The network ID for tracking redirects
            after_rowid: Row ID to search after
            timeout: Maximum time to wait

        Returns:
            Dict with next event info or None if nothing found
        """
        if not self.cdp:
            return None

        start = time.time()

        while time.time() - start < timeout:
            try:
                # Check for response stage (same requestId)
                response = self.cdp.query(
                    """
                    SELECT 
                        rowid,
                        json_extract_string(event, '$.params.responseStatusCode') as status
                    FROM events
                    WHERE json_extract_string(event, '$.method') = 'Fetch.requestPaused'
                      AND json_extract_string(event, '$.params.requestId') = ?
                      AND json_extract_string(event, '$.params.responseStatusCode') IS NOT NULL
                      AND rowid > ?
                    LIMIT 1
                """,
                    [request_id, after_rowid],
                )

                if response and len(response) > 0:
                    return {
                        "rowid": response[0][0],
                        "type": "response",
                        "status": response[0][1],
                        "description": f"Response stage ready (status {response[0][1]})",
                    }

                # Check for redirect (new requestId, same networkId)
                redirect = self.cdp.query(
                    """
                    SELECT 
                        rowid,
                        json_extract_string(event, '$.params.requestId') as new_request_id,
                        json_extract_string(event, '$.params.request.url') as url
                    FROM events
                    WHERE json_extract_string(event, '$.method') = 'Fetch.requestPaused'
                      AND json_extract_string(event, '$.params.networkId') = ?
                      AND json_extract_string(event, '$.params.redirectedRequestId') = ?
                      AND rowid > ?
                    LIMIT 1
                """,
                    [network_id, request_id, after_rowid],
                )

                if redirect and len(redirect) > 0:
                    url = redirect[0][2]
                    return {
                        "rowid": redirect[0][0],
                        "type": "redirect",
                        "request_id": redirect[0][1],
                        "url": url[:60] if url else None,
                        "description": f"Redirected to {url[:40]}..." if url else "Redirected",
                    }
            except Exception as e:
                logger.debug(f"Error during polling: {e}")
                # Continue polling on transient errors

            time.sleep(0.05)  # 50ms polling

        return None

    def fail_request(self, rowid: int, reason: str = "BlockedByClient") -> dict[str, Any]:
        """Explicitly fail a request.

        Args:
            rowid: Row ID from requests() table
            reason: CDP error reason

        Returns:
            Dict with failure status
        """
        if not self.enabled or not self.cdp:
            return {"error": "Fetch not enabled"}

        event = self.get_paused_event(rowid)
        if not event:
            return {"error": f"Event {rowid} not found"}

        request_id = event["params"]["requestId"]

        try:
            self.cdp.execute("Fetch.failRequest", {"requestId": request_id, "errorReason": reason})

            return {"failed": rowid, "reason": reason, "remaining": self.paused_count - 1}

        except Exception as e:
            logger.error(f"Failed to fail request {rowid}: {e}")
            return {"error": str(e)}

    def fulfill_request(
        self,
        rowid: int,
        response_code: int = 200,
        response_headers: list[dict[str, str]] | None = None,
        body: str = "",
    ) -> dict[str, Any]:
        """Fulfill a request with a custom response.

        Args:
            rowid: Row ID from requests() table
            response_code: HTTP response code
            response_headers: Response headers
            body: Response body

        Returns:
            Dict with fulfillment status
        """
        if not self.enabled or not self.cdp:
            return {"error": "Fetch not enabled"}

        event = self.get_paused_event(rowid)
        if not event:
            return {"error": f"Event {rowid} not found"}

        request_id = event["params"]["requestId"]

        try:
            import base64

            # Encode body to base64
            body_base64 = base64.b64encode(body.encode()).decode()

            params = {
                "requestId": request_id,
                "responseCode": response_code,
                "body": body_base64,
            }

            if response_headers:
                params["responseHeaders"] = response_headers

            self.cdp.execute("Fetch.fulfillRequest", params)

            return {"fulfilled": rowid, "response_code": response_code, "remaining": self.paused_count - 1}

        except Exception as e:
            logger.error(f"Failed to fulfill request {rowid}: {e}")
            return {"error": str(e)}


# No exports - internal service only
