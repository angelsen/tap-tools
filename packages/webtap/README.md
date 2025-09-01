# WebTap

Browser debugging via Chrome DevTools Protocol with native event storage and dynamic querying.

## Overview

WebTap connects to Chrome's debugging protocol and stores CDP events as-is in DuckDB, enabling powerful SQL queries and dynamic field discovery without complex transformations.

## Key Features

- **Native CDP Storage** - Events stored exactly as received in DuckDB
- **Dynamic Field Discovery** - Automatically indexes all field paths from events
- **Smart Filtering** - Built-in filters for ads, tracking, analytics noise
- **SQL Querying** - Direct DuckDB access for complex analysis
- **Chrome Extension** - Visual page selector and connection management
- **Python Inspection** - Full Python environment for data exploration

## Installation

```bash
# Install with uv
uv tool install webtap

# Or from source
cd packages/webtap
uv sync
```

## Quick Start

1. **Start Chrome with debugging**
```bash
# macOS
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222

# Linux  
google-chrome --remote-debugging-port=9222

# Windows
chrome.exe --remote-debugging-port=9222
```

2. **Launch WebTap**
```bash
webtap
```

3. **Connect and explore**
```python
>>> pages()                          # List available tabs
>>> connect(0)                       # Connect to first tab
>>> network()                        # View network requests (filtered)
>>> events(url="*api*", status=200)  # Query any CDP field dynamically
```

## Core Commands

### Connection & Navigation
```python
pages()                  # List Chrome tabs/workers
connect(page_id)         # Connect to a page
disconnect()             # Disconnect from Chrome
navigate(url)            # Navigate to URL
reload(ignore_cache=False)  # Reload page
back() / forward()       # Navigate history
```

### Dynamic Event Querying
```python
# Query ANY field across ALL event types
events(url="*github*")              # Find GitHub requests
events(status=404)                  # Find all 404s
events(type="xhr", method="POST")   # Find AJAX POSTs  
events(headers="*")                 # Extract all headers

# Field names are fuzzy-matched and case-insensitive
events(URL="*api*")     # Works! Finds 'url', 'URL', 'documentURL'
events(err="*")         # Finds 'error', 'errorText', 'err'
```

### Network Monitoring
```python
network()                           # Filtered network requests
network(all_filters=False)          # Show everything (noisy!)
network(filters=["ads", "tracking"]) # Specific filter categories
```

### Filter Management
```python
# Manage noise filters
filters()                           # Show current filters
filters(load=True)                  # Load from .webtap/filters.json
filters(add={"domain": "*doubleclick*", "category": "ads"})
filters(save=True)                  # Persist to disk

# Built-in categories: ads, tracking, analytics, telemetry, cdn, fonts, images
```

### Data Inspection
```python
# Inspect events by rowid
inspect(49)                         # View event details by rowid
inspect(50, expr="data['params']['response']['headers']")  # Extract field

# Response body inspection with Python expressions
body(49)                            # Get response body
body(49, expr="import json; json.loads(body)")  # Parse JSON
body(49, expr="len(body)")         # Check size

# Request interception
fetch()                             # Enable request interception
requests()                          # Show paused requests
resume("123.456")                   # Continue paused request
fail("123.456")                     # Fail paused request
```

### Console & JavaScript
```python
console()                           # View console messages
js("document.title")                # Evaluate JavaScript (returns value)
js("console.log('Hello')", wait_promise=False)  # Execute without waiting
clear()                             # Clear events (default)
clear(console=True)                 # Clear browser console
clear(events=True, console=True, cache=True)  # Clear everything
```

## Architecture

### Native CDP Storage Philosophy

```
Chrome Tab
    ↓ CDP Events (WebSocket)
DuckDB Storage (events table)
    ↓ SQL Queries + Field Discovery
Service Layer (WebTapService)
    ├── NetworkService - Request filtering
    ├── ConsoleService - Message handling
    ├── FetchService - Request interception
    └── BodyService - Response caching
    ↓
Commands (Thin Wrappers)
    ├── events() - Query any field
    ├── network() - Filtered requests  
    ├── console() - Messages
    ├── body() - Response bodies
    └── js() - JavaScript execution
    ↓
API Server (FastAPI on :8765)
    └── Chrome Extension Integration
```

### How It Works

1. **Events stored as-is** - No transformation, full CDP data preserved
2. **Field paths indexed** - Every unique path like `params.response.status` tracked
3. **Dynamic discovery** - Fuzzy matching finds fields without schemas
4. **SQL generation** - User queries converted to DuckDB JSON queries
5. **On-demand fetching** - Bodies, cookies fetched only when needed

## Advanced Usage

### Direct SQL Queries
```python
# Access DuckDB directly
sql = """
    SELECT json_extract_string(event, '$.params.response.url') as url,
           json_extract_string(event, '$.params.response.status') as status
    FROM events 
    WHERE json_extract_string(event, '$.method') = 'Network.responseReceived'
"""
results = state.cdp.query(sql)
```

### Field Discovery
```python
# See what fields are available
state.cdp.field_paths.keys()  # All discovered field names

# Find all paths for a field
state.cdp.discover_field_paths("url")
# Returns: ['params.request.url', 'params.response.url', 'params.documentURL', ...]
```

### Direct CDP Access
```python
# Send CDP commands directly
state.cdp.execute("Network.getResponseBody", {"requestId": "123"})
state.cdp.execute("Storage.getCookies", {})
state.cdp.execute("Runtime.evaluate", {"expression": "window.location.href"})
```

### Chrome Extension

Install the extension from `packages/webtap/extension/`:
1. Open `chrome://extensions/`
2. Enable Developer mode
3. Load unpacked → Select extension folder
4. Click extension icon to connect to pages

## Examples

### Find and Analyze API Calls
```python
>>> events(url="*api*", method="POST")
RowID  Method                      URL                              Status
-----  --------------------------  -------------------------------  ------
49     Network.requestWillBeSent   https://api.github.com/graphql  -
50     Network.responseReceived    https://api.github.com/graphql  200

>>> body(50, expr="import json; json.loads(body)['data']")
{'viewer': {'login': 'octocat', 'name': 'The Octocat'}}

>>> inspect(49)  # View full request details
```

### Debug Failed Requests
```python
>>> events(status=404)  # or status=500, etc.
>>> events(errorText="*")  # Find network errors
>>> events(type="Failed")  # Find failed resources
```

### Monitor Specific Domains
```python
>>> events(url="*myapi.com*")  # Your API
>>> events(url="*localhost*")  # Local development
>>> events(url="*stripe*")     # Payment APIs
```

### Extract Headers and Cookies
```python
>>> events(headers="*authorization*")  # Find auth headers
>>> state.cdp.execute("Storage.getCookies", {})  # Get all cookies
>>> events(setCookie="*")  # Find Set-Cookie headers
```

## Filter Configuration

WebTap includes aggressive default filters to reduce noise. Customize in `.webtap/filters.json`:

```json
{
  "ads": {
    "domains": ["*doubleclick*", "*googlesyndication*", "*adsystem*"],
    "types": ["Ping", "Beacon"]
  },
  "tracking": {
    "domains": ["*google-analytics*", "*segment*", "*mixpanel*"],
    "types": ["Image", "Script"]
  }
}
```

## Design Principles

1. **Store AS-IS** - No transformation of CDP events
2. **Query On-Demand** - Extract only what's needed
3. **Dynamic Discovery** - No predefined schemas
4. **SQL-First** - Leverage DuckDB's JSON capabilities
5. **Minimal Memory** - Store only CDP data

## Requirements

- Chrome/Chromium with debugging enabled
- Python 3.12+
- Dependencies: websocket-client, duckdb, replkit2, fastapi, uvicorn, beautifulsoup4

## Development

```bash
# Run from source
cd packages/webtap
uv run webtap

# API server starts automatically on port 8765
# Chrome extension connects to http://localhost:8765

# Type checking and linting
basedpyright packages/webtap/src/webtap
ruff check --fix packages/webtap/src/webtap
ruff format packages/webtap/src/webtap
```

## API Server

WebTap automatically starts a FastAPI server on port 8765 for Chrome extension integration:

- `GET /status` - Connection status
- `GET /pages` - List available Chrome tabs
- `POST /connect` - Connect to a page
- `POST /disconnect` - Disconnect from Chrome
- `POST /clear` - Clear events/console/cache
- `GET /fetch/paused` - Get paused requests
- `POST /filters/toggle/{category}` - Toggle filter categories

The API server runs in a background thread and doesn't block the REPL.

## License

MIT - See [LICENSE](../../LICENSE) for details.