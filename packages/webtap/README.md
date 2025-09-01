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
# Inspect cached events with Python
inspect(event="e1")                 # View event details
inspect(event="e2", expr="data['headers']")  # Extract specific field
inspect(expr="len(cache)")          # Run Python expressions

# Cache management
cache_list()                        # List all cached items
cache_list("request")               # List specific cache type
```

### Console & JavaScript
```python
console()                           # View console messages
js("document.title")                # Evaluate JavaScript (returns value)
js("console.log('Hello')", wait_return=False)  # Execute without return
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
Dynamic Commands
    ├── events() - Query any field
    ├── network() - Filtered requests  
    ├── console() - Messages
    └── inspect() - Python analysis
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
Event  Field                Value
-----  -------------------  ----------------------------------------
e1     params.request.url   https://api.github.com/graphql
e1     params.request.method POST
e1     params.response.status 200

>>> inspect(event="e1", expr="import json; json.loads(data.get('postData', '{}'))")
{'query': 'query { viewer { login } }', 'variables': {}}
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
- Dependencies: websocket-client, duckdb, replkit2

## Development

```bash
# Run from source
cd packages/webtap
uv run webtap

# Type checking and linting
basedpyright packages/webtap/src/webtap
ruff check --fix packages/webtap/src/webtap
ruff format packages/webtap/src/webtap
```

## License

MIT - See [LICENSE](../../LICENSE) for details.