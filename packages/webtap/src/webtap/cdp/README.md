# Chrome DevTools Protocol (CDP) Integration

This module handles the core CDP connection and event management for WebTap.

## Overview

The CDP module provides:
- WebSocket connection to Chrome's debugging port
- Event capture and storage in DuckDB
- Dynamic field discovery for flexible querying
- Native event storage (no transformation)

## Architecture

```
Chrome Browser
    ↓ (WebSocket)
CDPSession (session.py)
    ├── WebSocketApp (connection management)
    ├── DuckDB (event storage)
    └── Field Discovery (dynamic paths)
         ↓
Query Builder (query.py)
    └── SQL Generation
         ↓
WebTap Commands
```

## Core Components

### session.py
The main CDP session manager:
- Establishes WebSocket connection
- Stores events as-is in DuckDB
- Discovers field paths dynamically
- Handles CDP command execution

### query.py
Dynamic query builder:
- Fuzzy field matching
- SQL generation for JSON queries
- Cross-event correlation

### schema/
CDP protocol reference:
- Protocol version information
- Domain definitions (future)

## Philosophy: Native Storage

We store CDP events exactly as received:

```python
# CDP sends this
{
    "method": "Network.responseReceived",
    "params": {
        "requestId": "123.456",
        "response": {
            "status": 200,
            "headers": {...}
        }
    }
}

# We store it as-is in DuckDB
# No transformation, no data loss
```

## Event Domains

Currently capturing events from:

### Network Domain
- `Network.requestWillBeSent`
- `Network.responseReceived`
- `Network.loadingFinished`
- `Network.loadingFailed`

### Page Domain
- `Page.frameNavigated`
- `Page.domContentEventFired`
- `Page.loadEventFired`

### Runtime Domain
- `Runtime.consoleAPICalled`
- `Runtime.exceptionThrown`

### Fetch Domain
- `Fetch.requestPaused`
- `Fetch.authRequired`

### Storage Domain
- `Storage.cookiesChanged`
- `Storage.cacheStorageContentUpdated`

## Database Schema

### events table
```sql
CREATE TABLE events (
    rowid INTEGER PRIMARY KEY,
    event JSON,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

### Query Examples

```sql
-- Find all 404 responses
SELECT * FROM events 
WHERE json_extract_string(event, '$.params.response.status') = '404'

-- Get request/response pairs
SELECT 
    e1.rowid as request_row,
    e2.rowid as response_row,
    json_extract_string(e1.event, '$.params.request.url') as url
FROM events e1
JOIN events e2 ON 
    json_extract_string(e1.event, '$.params.requestId') = 
    json_extract_string(e2.event, '$.params.requestId')
WHERE 
    json_extract_string(e1.event, '$.method') = 'Network.requestWillBeSent'
    AND json_extract_string(e2.event, '$.method') = 'Network.responseReceived'
```

## Field Discovery

The system automatically discovers all field paths:

```python
# When we see this event:
{
    "method": "Network.responseReceived",
    "params": {
        "response": {
            "status": 200,
            "url": "https://example.com"
        }
    }
}

# We discover these paths:
# - method
# - params.response.status
# - params.response.url

# Users can then query with fuzzy matching:
events(status=200)  # Finds params.response.status
events(url="example")  # Finds params.response.url
```

## Connection Management

### Initialization
```python
cdp = CDPSession()
await cdp.connect("localhost", 9222, page_id)
```

### Event Flow
1. Chrome sends event over WebSocket
2. CDPSession receives in `on_message()`
3. Event stored in DuckDB immediately
4. Field paths extracted for discovery
5. Event available for querying

## CDP Command Execution

Direct command execution:
```python
# Get response body
result = cdp.execute("Network.getResponseBody", {
    "requestId": "123.456"
})

# Evaluate JavaScript
result = cdp.execute("Runtime.evaluate", {
    "expression": "document.title"
})
```

## Performance Considerations

- **Minimal Processing**: Events stored as-is
- **Lazy Evaluation**: Field discovery on-demand
- **Efficient Storage**: DuckDB's columnar format
- **Fast Queries**: JSON functions optimized in DuckDB

## Extension Points

### Adding New Domains
To capture events from additional CDP domains:

1. Enable the domain:
```python
cdp.execute("DOMStorage.enable")
```

2. Events automatically captured and stored

3. Query them:
```python
events(method="DOMStorage.*")
```

### Custom Event Processing
While we store events as-is, you can add custom processors:

```python
def process_network_event(event):
    # Custom logic here
    pass

# Register processor
cdp.register_processor("Network.*", process_network_event)
```

## Integration with SDP

The CDP module will work alongside the future SDP (Svelte Debug Protocol) module:

```
CDP Events (Network, DOM, Console)
    +
SDP Events (State, Components, Reactivity)
    ↓
Unified Event Stream in DuckDB
    ↓
Correlated Analysis
```

## Best Practices

1. **Don't Transform**: Store CDP data as-is
2. **Query Don't Parse**: Use SQL for extraction
3. **Discover Don't Define**: Let field paths emerge
4. **Correlate Don't Duplicate**: Link events by IDs

## Debugging

### Enable verbose logging
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Check connection
```python
cdp.connected  # Should be True
cdp.ws.sock.connected  # WebSocket status
```

### Inspect stored events
```python
cdp.query("SELECT COUNT(*) FROM events")
cdp.query("SELECT * FROM events ORDER BY rowid DESC LIMIT 5")
```

## Future Enhancements

- [ ] Event compression for long sessions
- [ ] Streaming to external storage
- [ ] Real-time event subscriptions
- [ ] Custom domain definitions
- [ ] Event replay functionality