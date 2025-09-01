# WebTap Vision: Work WITH Chrome DevTools Protocol

## Core Philosophy

**Store CDP events as-is. Transform minimally. Query on-demand.**

Instead of transforming CDP's complex nested structures into our own models, we embrace CDP's native format. We store events mostly unchanged, extract minimal data for tables, and query additional data on-demand.

## The Problem We're Solving

CDP sends rich, nested event data. Previous approaches tried to:
1. Transform everything into flat models
2. Create abstraction layers over CDP
3. Build complex query engines
4. Format data for display

This led to:
- Loss of CDP's rich information
- Complex transformation logic
- Over-engineered abstractions
- Unnecessary memory usage

## The Solution: Native CDP Storage

### 1. Store Events As-Is

```python
# CDP gives us this - we keep it!
{
    "method": "Network.responseReceived",
    "params": {
        "requestId": "123.456", 
        "response": {
            "status": 200,
            "headers": {...},
            "mimeType": "application/json",
            "timing": {...}
        }
    }
}
```

### 2. Minimal Summaries for Tables

Extract only what's needed for table display:
```python
NetworkSummary(
    id="123.456",
    method="GET",
    status=200,
    url="https://api.example.com/data",
    type="json",
    size=1234
)
```

Keep the full CDP events attached for detail views.

### 3. On-Demand Queries

Some data isn't in the event stream:
- Response bodies: `Network.getResponseBody`
- Cookies: `Storage.getCookies` 
- LocalStorage: `DOMStorage.getDOMStorageItems`
- JavaScript evaluation: `Runtime.evaluate`

Query these when needed, not preemptively.

## Architecture

```
                    ┌─────────────────┐
                    │   Chrome Tab    │
                    └────────┬────────┘
                             │ CDP Events
                    ┌────────▼────────┐
                    │   WebSocket     │
                    │  (WebSocketApp) │
                    └────────┬────────┘
                             │ Raw Events
                    ┌────────▼────────┐
                    │  DuckDB Storage │
                    │  (events table) │
                    └────────┬────────┘
                             │ SQL Queries
                ┌────────────┼────────────┐
                │            │            │
        ┌───────▼──────┐ ┌───▼───┐ ┌──────▼──────┐
        │   Commands   │ │ Tables│ │Detail Views │
        │network()     │ │       │ │             │
        │console()     │ │Minimal│ │Full CDP Data│
        │storage()     │ │Summary│ │+ On-Demand  │
        └──────────────┘ └───────┘ └─────────────┘
```

## Data Flow Examples

### Network Request Lifecycle

```python
# 1. Request sent - store as-is in DuckDB
db.execute("INSERT INTO events VALUES (?)", [json.dumps({
    "method": "Network.requestWillBeSent",
    "params": {...}  # Full CDP data
})])

# 2. Response received - store as-is
db.execute("INSERT INTO events VALUES (?)", [json.dumps({
    "method": "Network.responseReceived", 
    "params": {...}  # Full CDP data
})])

# 3. Query for table view - SQL on JSON
db.execute("""
    SELECT 
        json_extract_string(event, '$.params.requestId') as id,
        json_extract_string(event, '$.params.response.status') as status,
        json_extract_string(event, '$.params.response.url') as url
    FROM events 
    WHERE json_extract_string(event, '$.method') = 'Network.responseReceived'
""")

# 4. Detail view - get all events for request
db.execute("""
    SELECT event FROM events 
    WHERE json_extract_string(event, '$.params.requestId') = ?
""", [request_id])

# 5. Body fetch - on-demand CDP call
cdp.execute("Network.getResponseBody", {"requestId": "123.456"})
```

### Console Message

```python
# 1. Store as-is
console_events.append({
    "method": "Runtime.consoleAPICalled",
    "params": {
        "type": "error",
        "args": [{"type": "string", "value": "Failed to fetch"}],
        "stackTrace": {...}
    }
})

# 2. Table view - minimal summary
ConsoleSummary(
    id="console-123",
    level="error",
    message="Failed to fetch",
    source="console"
)

# 3. Detail view - full CDP data
{
    "summary": summary,
    "raw": console_events[i],  # Full CDP event with stack trace
}
```

## Benefits

1. **No Information Loss** - Full CDP data always available
2. **Minimal Memory** - Only store what CDP sends
3. **Simple Code** - No complex transformations
4. **Fast Tables** - Minimal summaries render quickly
5. **Rich Details** - Full CDP data for debugging
6. **On-Demand Loading** - Expensive operations only when needed
7. **Future Proof** - New CDP features automatically available

## Implementation Principles

### DO:
- Store CDP events as-is
- Build minimal summaries for tables
- Query additional data on-demand
- Group events by correlation ID (requestId)
- Let Replkit2 handle display

### DON'T:
- Transform CDP structure unnecessarily
- Fetch data preemptively
- Create abstraction layers
- Build complex query engines
- Format data for display

## File Structure

```
webtap/
├── VISION.md           # This file
├── __init__.py         # Module initialization + API server startup
├── app.py              # REPL app with WebTapState
├── api.py              # FastAPI server for Chrome extension
├── filters.py          # Filter management system
├── cdp/
│   ├── __init__.py
│   ├── session.py      # CDPSession with DuckDB storage
│   ├── query.py        # Dynamic query builder
│   └── schema/         # CDP protocol reference
│       ├── README.md
│       └── cdp_version.json
├── services/           # Service layer (business logic)
│   ├── __init__.py
│   ├── main.py         # WebTapService orchestrator
│   ├── network.py      # Network request handling
│   ├── console.py      # Console message handling
│   ├── fetch.py        # Request interception
│   └── body.py         # Response body caching
└── commands/           # Thin command wrappers
    ├── __init__.py
    ├── _errors.py      # Unified error handling
    ├── _markdown.py    # Markdown elements
    ├── _symbols.py     # ASCII symbol registry
    ├── _utils.py       # Shared utilities
    ├── connection.py   # connect, disconnect, pages
    ├── navigation.py   # navigate, reload, back, forward
    ├── network.py      # network() command
    ├── console.py      # console() command
    ├── events.py       # events() dynamic querying
    ├── inspect.py      # inspect() event details
    ├── javascript.py   # js() execution
    ├── body.py         # body() response inspection
    ├── fetch.py        # fetch(), requests(), resume()
    └── filters.py      # filters() management
```

## Success Metrics

- **Lines of Code**: < 500 (excluding commands)
- **Transformation Logic**: < 100 lines
- **Memory Usage**: Only what CDP sends
- **Response Time**: Instant for tables, < 100ms for details
- **CDP Coverage**: 100% of CDP data accessible