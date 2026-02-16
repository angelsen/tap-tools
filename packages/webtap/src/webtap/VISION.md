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
      ┌─────────────────────────────────────┐
      │           Chrome Browser            │
      │  ┌───────┐  ┌───────┐┌─────┐        │
      │  │ Tab 1 │  │ Tab 2 ││ SW  │        │
      │  └───┬───┘  └───┬───┘└──┬──┘        │
      └──────┼──────────┼───────┼───────────┘
             └──────────┼───────┘
                        │ CDP (one WS per browser)
               ┌────────▼────────┐
               │ BrowserSession  │  Watch/unwatch, target discovery,
               │ (browser.py)    │  pattern matching, auto-attach
               └────────┬────────┘
                        │ Multiplexed sessions
            ┌───────────┼───────────┐
       ┌────▼─────┐ ┌───▼────┐ ┌───▼────┐
       │CDPSession│ │CDPSess.│ │CDPSess.│  Per-target DuckDB
       │  Tab 1   │ │ Tab 2  │ │  SW    │  event storage
       └────┬─────┘ └───┬────┘ └───┬────┘
            └───────────┼──────────┘
                        │ SQL Queries
           ┌────────────┼───────────┐
           │            │           │
   ┌───────▼──────┐ ┌───▼───┐ ┌─────▼───────┐
   │   Commands   │ │ Table │ │ Detail View │
   │ network()    │ │       │ │             │
   │ console()    │ │Minimal│ │Full CDP Data│
   │ js()         │ │Summary│ │+ On-Demand  │
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
├── __init__.py         # Entry point, CLI commands (controls, controls-setup)
├── __main__.py         # Python -m webtap support
├── app.py              # REPL app entry point
├── client.py           # RPCClient for JSON-RPC communication
├── daemon.py           # Background daemon process
├── filters.py          # Filter management system
├── notices.py          # Notice management (type definitions, NoticeManager)
├── targets.py          # Target ID utilities (make_target, parse_target)
├── api/                # FastAPI server (runs in daemon)
│   ├── app.py          # FastAPI app & shared state
│   ├── server.py       # Server init, RPC wiring, GET /prompt endpoint
│   ├── state.py        # State snapshot hash & SSE formatting
│   └── sse.py          # Server-sent events for live updates
├── rpc/                # JSON-RPC 2.0 framework
│   ├── framework.py    # RPCFramework class & method registration
│   ├── handlers.py     # All RPC method handlers
│   └── errors.py       # RPCError and error codes
├── cdp/
│   ├── browser.py      # BrowserSession (one WS per port, session multiplexing)
│   ├── session.py      # CDPSession with DuckDB storage
│   ├── har.py          # HAR view aggregation (har_entries, har_summary)
│   └── schema/         # CDP protocol reference
├── services/           # Service layer (business logic)
│   ├── main.py         # WebTapService orchestrator
│   ├── connection.py   # ConnectionManager & per-target state
│   ├── network.py      # Network request handling
│   ├── console.py      # Console message handling
│   ├── fetch.py        # Request interception (capture, block, mock)
│   ├── dom.py          # DOM inspection & element selection
│   ├── watcher.py      # ChromeWatcher target discovery
│   ├── state_snapshot.py  # Frozen dataclass for thread-safe SSE
│   ├── daemon_state.py # Daemon state persistence
│   ├── _utils.py       # Shared service utilities
│   └── setup/          # Browser/extension setup commands
│       ├── browser.py  # run-browser command
│       ├── chrome.py   # Chrome discovery & profile management
│       ├── desktop.py  # Desktop launcher generation
│       └── platform.py # Platform detection
├── commands/           # Thin command wrappers
│   ├── _builders.py    # Response builders & validators
│   ├── _utils.py       # Shared utilities & expression eval
│   ├── _code_generation.py  # JSON/code generation helpers
│   ├── _tips.py        # Documentation parser (TIPS.md)
│   ├── connection.py   # watch, unwatch, targets, watching, clear
│   ├── navigation.py   # navigate, reload, back, forward
│   ├── network.py      # network(search=) with header filtering
│   ├── console.py      # console() command
│   ├── request.py      # request() field selection + expr
│   ├── entry.py        # entry() console detail view
│   ├── javascript.py   # js() execution
│   ├── fetch.py        # fetch(), requests(), resume(), fail()
│   ├── filters.py      # filters() management
│   ├── selections.py   # selections/browser() element selection
│   ├── to_model.py     # to_model() Pydantic generation
│   ├── quicktype.py    # quicktype() type generation
│   ├── launch.py       # run-browser, debug-android CLI commands
│   ├── extension.py    # install-extension CLI command
│   └── setup.py        # setup-browser CLI command
├── utils/
│   └── ports.py        # Port discovery & allocation
└── extension/          # Chrome extension (sidepanel UI)
    ├── manifest.json
    ├── background.js   # Service worker
    ├── main.js         # Sidepanel entry point
    ├── sidepanel.html
    ├── sidepanel.css
    ├── client.js       # RPC client for daemon communication
    ├── bind.js         # Data binding utilities
    ├── datatable.js    # Reusable data table component
    ├── controllers/    # UI controllers (one per section)
    │   ├── targets.js  # Target discovery & watch/unwatch
    │   ├── watching.js # Active watched targets display
    │   ├── patterns.js # URL pattern watch management
    │   ├── network.js  # Network request table
    │   ├── console.js  # Console messages table
    │   ├── capture.js  # Fetch interception controls
    │   ├── filters.js  # Filter group management
    │   ├── selections.js  # DOM element selection
    │   ├── notices.js  # Notice display
    │   ├── header.js   # Connection status header
    │   ├── tabs.js     # Tab navigation
    │   └── theme.js    # Dark/light theme
    └── lib/            # Shared extension utilities
        ├── ui.js       # DOM helpers
        ├── utils.js    # General utilities
        ├── target-utils.js  # Target ID formatting
        ├── rpc/errors.js    # RPC error handling
        └── table/      # Table rendering library
```

## Success Metrics

- **Lines of Code**: < 500 (excluding commands)
- **Transformation Logic**: < 100 lines
- **Memory Usage**: Only what CDP sends
- **Response Time**: Instant for tables, < 100ms for details
- **CDP Coverage**: 100% of CDP data accessible
