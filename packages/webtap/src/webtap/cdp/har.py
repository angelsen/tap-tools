"""HAR view creation for DuckDB."""

import logging

logger = logging.getLogger(__name__)

# HAR entries view - aggregates CDP events into HAR-like structure
_HAR_ENTRIES_SQL = """
CREATE OR REPLACE VIEW har_entries AS
WITH
-- Paused Fetch events (unresolved)
paused_fetch AS (
    SELECT
        json_extract_string(event, '$.params.networkId') as network_id,
        rowid as paused_id,
        json_extract_string(event, '$.params.responseStatusCode') as fetch_status,
        json_extract(event, '$.params.responseHeaders') as fetch_response_headers,
        CASE
            WHEN json_extract_string(event, '$.params.responseStatusCode') IS NOT NULL
            THEN 'Response'
            ELSE 'Request'
        END as pause_stage,
        json_extract_string(event, '$.params.requestId') as fetch_request_id
    FROM events
    WHERE method = 'Fetch.requestPaused'
),

-- Resolved Fetch events (continued, failed, or fulfilled)
resolved_fetch AS (
    SELECT DISTINCT json_extract_string(event, '$.params.requestId') as network_id
    FROM events
    WHERE method IN ('Network.loadingFinished', 'Network.loadingFailed')
),

-- Only unresolved paused events (latest per networkId)
active_paused AS (
    SELECT pf.*
    FROM paused_fetch pf
    WHERE pf.network_id IS NOT NULL
      AND pf.network_id NOT IN (SELECT network_id FROM resolved_fetch WHERE network_id IS NOT NULL)
    QUALIFY ROW_NUMBER() OVER (PARTITION BY pf.network_id ORDER BY pf.paused_id DESC) = 1
),

-- HTTP Request: extract from requestWillBeSent
http_requests AS (
    SELECT
        json_extract_string(event, '$.params.requestId') as request_id,
        MIN(rowid) as first_rowid,
        'http' as protocol,
        MAX(json_extract_string(event, '$.params.wallTime')) as started_datetime,
        MAX(json_extract_string(event, '$.params.timestamp')) as started_timestamp,
        MAX(json_extract_string(event, '$.params.request.method')) as method,
        MAX(json_extract_string(event, '$.params.request.url')) as url,
        MAX(json_extract(event, '$.params.request.headers')) as request_headers,
        MAX(json_extract_string(event, '$.params.request.postData')) as post_data,
        MAX(json_extract_string(event, '$.params.type')) as resource_type
    FROM events
    WHERE method = 'Network.requestWillBeSent'
    GROUP BY json_extract_string(event, '$.params.requestId')
),

-- HTTP Response: extract from responseReceived
http_responses AS (
    SELECT
        json_extract_string(event, '$.params.requestId') as request_id,
        MAX(json_extract_string(event, '$.params.response.status')) as status,
        MAX(json_extract_string(event, '$.params.response.statusText')) as status_text,
        MAX(json_extract(event, '$.params.response.headers')) as response_headers,
        MAX(json_extract_string(event, '$.params.response.mimeType')) as mime_type,
        MAX(json_extract(event, '$.params.response.timing')) as timing
    FROM events
    WHERE method = 'Network.responseReceived'
    GROUP BY json_extract_string(event, '$.params.requestId')
),

-- HTTP Finished: timing and size
http_finished AS (
    SELECT
        json_extract_string(event, '$.params.requestId') as request_id,
        MAX(json_extract_string(event, '$.params.timestamp')) as finished_timestamp,
        MAX(json_extract_string(event, '$.params.encodedDataLength')) as final_size
    FROM events
    WHERE method = 'Network.loadingFinished'
    GROUP BY json_extract_string(event, '$.params.requestId')
),

-- HTTP Failed: error info
http_failed AS (
    SELECT
        json_extract_string(event, '$.params.requestId') as request_id,
        MAX(json_extract_string(event, '$.params.errorText')) as error_text
    FROM events
    WHERE method = 'Network.loadingFailed'
    GROUP BY json_extract_string(event, '$.params.requestId')
),

-- WebSocket Created
ws_created AS (
    SELECT
        json_extract_string(event, '$.params.requestId') as request_id,
        MIN(rowid) as first_rowid,
        'websocket' as protocol,
        MAX(json_extract_string(event, '$.params.url')) as url
    FROM events
    WHERE method = 'Network.webSocketCreated'
    GROUP BY json_extract_string(event, '$.params.requestId')
),

-- WebSocket Handshake
ws_handshake AS (
    SELECT
        json_extract_string(event, '$.params.requestId') as request_id,
        MAX(json_extract_string(event, '$.params.wallTime')) as started_datetime,
        MAX(json_extract_string(event, '$.params.timestamp')) as started_timestamp,
        MAX(json_extract(event, '$.params.request.headers')) as request_headers,
        MAX(json_extract_string(event, '$.params.response.status')) as status,
        MAX(json_extract(event, '$.params.response.headers')) as response_headers
    FROM events
    WHERE method IN ('Network.webSocketWillSendHandshakeRequest', 'Network.webSocketHandshakeResponseReceived')
    GROUP BY json_extract_string(event, '$.params.requestId')
),

-- WebSocket Frame Stats (aggregated)
ws_frames AS (
    SELECT
        json_extract_string(event, '$.params.requestId') as request_id,
        SUM(CASE WHEN method = 'Network.webSocketFrameSent' THEN 1 ELSE 0 END) as frames_sent,
        SUM(CASE WHEN method = 'Network.webSocketFrameReceived' THEN 1 ELSE 0 END) as frames_received,
        SUM(LENGTH(COALESCE(json_extract_string(event, '$.params.response.payloadData'), ''))) as total_bytes
    FROM events
    WHERE method IN ('Network.webSocketFrameSent', 'Network.webSocketFrameReceived')
    GROUP BY json_extract_string(event, '$.params.requestId')
),

-- WebSocket Closed
ws_closed AS (
    SELECT
        json_extract_string(event, '$.params.requestId') as request_id,
        MAX(json_extract_string(event, '$.params.timestamp')) as closed_timestamp
    FROM events
    WHERE method = 'Network.webSocketClosed'
    GROUP BY json_extract_string(event, '$.params.requestId')
),

-- Combine HTTP entries
http_entries AS (
    SELECT
        req.first_rowid as id,
        req.request_id,
        req.protocol,
        req.method,
        req.url,
        -- Use Fetch status if paused at Response, otherwise Network status
        CAST(COALESCE(ap.fetch_status, resp.status, '0') AS INTEGER) as status,
        resp.status_text,
        req.resource_type as type,
        CAST(COALESCE(fin.final_size, '0') AS INTEGER) as size,
        CASE
            WHEN fin.finished_timestamp IS NOT NULL
            THEN CAST((CAST(fin.finished_timestamp AS DOUBLE) - CAST(req.started_timestamp AS DOUBLE)) * 1000 AS INTEGER)
            ELSE NULL
        END as time_ms,
        -- State priority: paused > failed > complete > loading > pending
        CASE
            WHEN ap.paused_id IS NOT NULL THEN 'paused'
            WHEN fail.error_text IS NOT NULL THEN 'failed'
            WHEN fin.finished_timestamp IS NOT NULL THEN 'complete'
            WHEN resp.status IS NOT NULL THEN 'loading'
            ELSE 'pending'
        END as state,
        ap.pause_stage,
        ap.paused_id,
        req.request_headers,
        req.post_data,
        -- Prefer Fetch response headers if at Response stage
        COALESCE(ap.fetch_response_headers, resp.response_headers) as response_headers,
        resp.mime_type,
        resp.timing,
        fail.error_text,
        CAST(NULL AS BIGINT) as frames_sent,
        CAST(NULL AS BIGINT) as frames_received,
        CAST(NULL AS BIGINT) as ws_total_bytes
    FROM http_requests req
    LEFT JOIN http_responses resp ON req.request_id = resp.request_id
    LEFT JOIN http_finished fin ON req.request_id = fin.request_id
    LEFT JOIN http_failed fail ON req.request_id = fail.request_id
    LEFT JOIN active_paused ap ON req.request_id = ap.network_id
),

-- Combine WebSocket entries
websocket_entries AS (
    SELECT
        ws.first_rowid as id,
        ws.request_id,
        ws.protocol,
        'WS' as method,
        ws.url,
        CAST(COALESCE(hs.status, '101') AS INTEGER) as status,
        CAST(NULL AS VARCHAR) as status_text,
        'WebSocket' as type,
        CAST(COALESCE(wf.total_bytes, 0) AS INTEGER) as size,
        CASE
            WHEN wc.closed_timestamp IS NOT NULL
            THEN CAST((CAST(wc.closed_timestamp AS DOUBLE) - CAST(hs.started_timestamp AS DOUBLE)) * 1000 AS INTEGER)
            ELSE NULL
        END as time_ms,
        CASE
            WHEN wc.closed_timestamp IS NOT NULL THEN 'closed'
            WHEN hs.status IS NOT NULL THEN 'open'
            ELSE 'connecting'
        END as state,
        CAST(NULL AS VARCHAR) as pause_stage,
        CAST(NULL AS BIGINT) as paused_id,
        hs.request_headers,
        CAST(NULL AS VARCHAR) as post_data,
        hs.response_headers,
        'websocket' as mime_type,
        CAST(NULL AS JSON) as timing,
        CAST(NULL AS VARCHAR) as error_text,
        wf.frames_sent,
        wf.frames_received,
        wf.total_bytes as ws_total_bytes
    FROM ws_created ws
    LEFT JOIN ws_handshake hs ON ws.request_id = hs.request_id
    LEFT JOIN ws_frames wf ON ws.request_id = wf.request_id
    LEFT JOIN ws_closed wc ON ws.request_id = wc.request_id
)

SELECT * FROM http_entries
UNION ALL
SELECT * FROM websocket_entries
ORDER BY id DESC
"""

# HAR summary view - lightweight list for network() command
_HAR_SUMMARY_SQL = """
CREATE OR REPLACE VIEW har_summary AS
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
    frames_received
FROM har_entries
"""


def create_har_views(db_execute) -> None:
    """Create HAR-based aggregation views in DuckDB.

    Args:
        db_execute: Function to execute SQL (session._db_execute)

    Creates:
        - har_entries: Full HAR structure with all fields
        - har_summary: Lightweight list view for network() command
    """
    db_execute(_HAR_ENTRIES_SQL, wait_result=True)
    db_execute(_HAR_SUMMARY_SQL, wait_result=True)
    logger.debug("HAR views created")


__all__ = ["create_har_views"]
