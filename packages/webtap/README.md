# webtap

Browser debugging via Chrome DevTools Protocol with native event storage and dynamic querying.

## ✨ Features

- 🔍 **Native CDP Storage** - Events stored exactly as received in DuckDB
- 🎯 **Dynamic Field Discovery** - Automatically indexes all field paths from events
- 🚫 **Smart Filtering** - Built-in filters for ads, tracking, analytics noise
- 📊 **SQL Querying** - Direct DuckDB access for complex analysis
- 🔌 **MCP Ready** - Tools and resources for Claude/LLMs
- 🎨 **Rich Display** - Tables, alerts, and formatted output
- 🐍 **Python Inspection** - Full Python environment for data exploration

## 📋 Prerequisites

Required system dependencies:
- **google-chrome-stable** or **chromium** - Browser with DevTools Protocol support

```bash
# macOS
brew install --cask google-chrome

# Ubuntu/Debian
wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
sudo sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list'
sudo apt update
sudo apt install google-chrome-stable

# Arch Linux
yay -S google-chrome  # or google-chrome-stable from AUR

# Fedora
sudo dnf install google-chrome-stable
```

## 📦 Installation

```bash
# Install via uv tool (recommended)
uv tool install webtap-tool

# Or with pipx
pipx install webtap-tool

# Update to latest
uv tool upgrade webtap-tool

# Uninstall
uv tool uninstall webtap-tool
```

## 🚀 Quick Start

```bash
# 1. Install webtap
uv tool install webtap-tool

# 2. Optional: Setup helpers (first time only)
webtap --cli setup-filters       # Download default filter configurations
webtap --cli setup-extension     # Download Chrome extension files
webtap --cli setup-chrome        # Install Chrome wrapper for debugging

# 3. Launch Chrome with debugging
webtap --cli run-chrome          # Or manually: google-chrome-stable --remote-debugging-port=9222

# 4. Start webtap REPL
webtap

# 5. Connect and explore
>>> pages()                          # List available Chrome pages
>>> connect(0)                       # Connect to first page
>>> network()                        # View network requests (filtered)
>>> console()                        # View console messages
>>> events({"url": "*api*"})         # Query any CDP field dynamically
```

## 🔌 MCP Setup for Claude

```bash
# Quick setup with Claude CLI
claude mcp add webtap -- webtap --mcp
```

Or manually configure Claude Desktop (`~/Library/Application Support/Claude/claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "webtap": {
      "command": "webtap",
      "args": ["--mcp"]
    }
  }
}
```

## 🎮 Usage

### Interactive REPL
```bash
webtap                     # Start REPL
webtap --mcp               # Start as MCP server
```

### CLI Commands
```bash
webtap --cli setup-filters      # Download filter configurations
webtap --cli setup-extension    # Download Chrome extension
webtap --cli setup-chrome       # Install Chrome wrapper script
webtap --cli run-chrome         # Launch Chrome with debugging
webtap --cli --help            # Show all CLI commands
```

### Commands
```python
>>> pages()                          # List available Chrome pages
>>> connect(0)                       # Connect to first page
>>> network()                        # View network requests (filtered)
>>> console()                        # View console messages
>>> events({"url": "*api*"})         # Query any CDP field dynamically
>>> body(50)                         # Get response body
>>> inspect(49)                      # View event details
>>> js("document.title")             # Execute JavaScript
```

### Command Reference

| Command | Description |
|---------|------------|
| `pages()` | List available Chrome pages |
| `connect(page=0)` | Connect to page by index |
| `disconnect()` | Disconnect from current page |
| `navigate(url)` | Navigate to URL |
| `network(no_filters=False)` | View network requests |
| `console()` | View console messages |
| `events(filters)` | Query events dynamically |
| `inspect(rowid, expr=None)` | Inspect event details |
| `body(response_id, expr=None)` | Get response body |
| `js(code, wait_return=True)` | Execute JavaScript |
| `filters(action="list")` | Manage noise filters |
| `clear(events=True)` | Clear events/console/cache |

## Core Commands

### Connection & Navigation
```python
pages()                      # List Chrome pages
connect(0)                   # Connect by index (shorthand)
connect(page=1)              # Connect by index (explicit)
connect(page_id="xyz")       # Connect by page ID  
disconnect()                 # Disconnect from current page
navigate("https://...")      # Navigate to URL
reload(ignore_cache=False)   # Reload page
back() / forward()           # Navigate history
page()                       # Show current page info
```

### Dynamic Event Querying
```python
# Query ANY field across ALL event types using dict filters
events({"url": "*github*"})              # Find GitHub requests
events({"status": 404})                  # Find all 404s
events({"type": "xhr", "method": "POST"})   # Find AJAX POSTs  
events({"headers": "*"})                 # Extract all headers

# Field names are fuzzy-matched and case-insensitive
events({"URL": "*api*"})     # Works! Finds 'url', 'URL', 'documentURL'
events({"err": "*"})         # Finds 'error', 'errorText', 'err'
```

### Network Monitoring
```python
network()                              # Filtered network requests (default)
network(no_filters=True)               # Show everything (noisy!)
network(filters=["ads", "tracking"])   # Specific filter categories
```

### Filter Management
```python
# Manage noise filters
filters()                                # Show current filters (default action="list")
filters(action="load")                   # Load from .webtap/filters.json
filters(action="add", config={"domain": "*doubleclick*", "category": "ads"})
filters(action="save")                   # Persist to disk
filters(action="toggle", config={"category": "ads"})  # Toggle category

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
fetch("enable")                     # Enable request interception
fetch("disable")                    # Disable request interception
requests()                          # Show paused requests
resume(123)                         # Continue paused request by ID
fail(123)                           # Fail paused request by ID
```

### Console & JavaScript
```python
console()                           # View console messages
js("document.title")                # Evaluate JavaScript (returns value)
js("console.log('Hello')", wait_return=False)  # Execute without waiting
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

### List and Connect to Pages
```python
>>> pages()
## Chrome Pages

| Index | Title                | URL                            | ID     | Connected |
|:------|:---------------------|:-------------------------------|:-------|:----------|
| 0     | Messenger            | https://www.m...1743198803269/ | DC8... | No        |
| 1     | GitHub - replkit2    | https://githu...elsen/replkit2 | DD4... | No        |
| 2     | YouTube Music        | https://music.youtube.com/     | F83... | No        |

_3 pages available_
<pages: 1 fields>

>>> connect(1)
## Connection Established

**Page:** GitHub - angelsen/replkit2

**URL:** https://github.com/angelsen/replkit2
<connect: 1 fields>
```

### Monitor Network Traffic
```python
>>> network()
## Network Requests

| ID   | ReqID        | Method | Status | URL                                             | Type     | Size |
|:-----|:-------------|:-------|:-------|:------------------------------------------------|:---------|:-----|
| 3264 | 682214.9033  | GET    | 200    | https://api.github.com/graphql                  | Fetch    | 22KB |
| 2315 | 682214.8985  | GET    | 200    | https://api.github.com/repos/angelsen/replkit2  | Fetch    | 16KB |
| 359  | 682214.8638  | GET    | 200    | https://github.githubassets.com/assets/app.js   | Script   | 21KB |

_3 requests_

### Next Steps

- **Analyze responses:** `body(3264)` - fetch response body
- **Parse HTML:** `body(3264, "bs4(body, 'html.parser').find('title').text")`
- **Extract JSON:** `body(3264, "json.loads(body)['data']")`
- **Find patterns:** `body(3264, "re.findall(r'/api/\\w+', body)")`
- **Decode JWT:** `body(3264, "jwt.decode(body, options={'verify_signature': False})")`
- **Search events:** `events({'url': '*api*'})` - find all API calls
- **Intercept traffic:** `fetch('enable')` then `requests()` - pause and modify
<network: 1 fields>
```

### View Console Messages
```python
>>> console()
## Console Messages

| ID   | Level      | Source   | Message                                                         | Time     |
|:-----|:-----------|:---------|:----------------------------------------------------------------|:---------|
| 5939 | WARNING    | security | An iframe which has both allow-scripts and allow-same-origin... | 11:42:46 |
| 2319 | LOG        | console  | API request completed                                           | 11:42:40 |
| 32   | ERROR      | network  | Failed to load resource: the server responded with a status...  | 12:47:41 |

_3 messages_

### Next Steps

- **Inspect error:** `inspect(32)` - view full stack trace
- **Find all errors:** `events({'level': 'error'})` - filter console errors
- **Extract stack:** `inspect(32, "data.get('stackTrace', {})")`
- **Search messages:** `events({'message': '*failed*'})` - pattern match
- **Check network:** `network()` - may show failed requests causing errors
<console: 1 fields>
```

### Find and Analyze API Calls
```python
>>> events({"url": "*api*", "method": "POST"})
## Query Results

| RowID | Method                      | URL                             | Status |
|:------|:----------------------------|:--------------------------------|:-------|
| 49    | Network.requestWillBeSent   | https://api.github.com/graphql  | -      |
| 50    | Network.responseReceived    | https://api.github.com/graphql  | 200    |

_2 events_
<events: 1 fields>

>>> body(50, expr="import json; json.loads(body)['data']")
{'viewer': {'login': 'octocat', 'name': 'The Octocat'}}

>>> inspect(49)  # View full request details
```

### Debug Failed Requests
```python
>>> events({"status": 404})
## Query Results

| RowID | Method                   | URL                               | Status |
|:------|:-------------------------|:----------------------------------|:-------|
| 32    | Network.responseReceived | https://api.example.com/missing   | 404    |
| 29    | Network.responseReceived | https://api.example.com/notfound  | 404    |

_2 events_
<events: 1 fields>

>>> events({"errorText": "*"})  # Find network errors
>>> events({"type": "Failed"})  # Find failed resources
```

### Monitor Specific Domains
```python
>>> events({"url": "*myapi.com*"})  # Your API
>>> events({"url": "*localhost*"})  # Local development
>>> events({"url": "*stripe*"})     # Payment APIs
```

### Extract Headers and Cookies
```python
>>> events({"headers": "*authorization*"})  # Find auth headers
>>> state.cdp.execute("Storage.getCookies", {})  # Get all cookies
>>> events({"setCookie": "*"})  # Find Set-Cookie headers
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

## 🏗️ Architecture

Built on [ReplKit2](https://github.com/angelsen/replkit2) for dual REPL/MCP functionality.

**Key Design:**
- **Store AS-IS** - No transformation of CDP events
- **Query On-Demand** - Extract only what's needed
- **Dynamic Discovery** - No predefined schemas
- **SQL-First** - Leverage DuckDB's JSON capabilities
- **Minimal Memory** - Store only CDP data

## 📚 Documentation

- [Architecture](ARCHITECTURE.md) - System design
- [Vision](src/webtap/VISION.md) - Design philosophy
- [Services](src/webtap/services/) - Service layer implementations
- [Commands](src/webtap/commands/) - Command implementations

## 🛠️ Development

```bash
# Clone repository
git clone https://github.com/angelsen/tap-tools
cd tap-tools

# Install for development
uv sync --package webtap

# Run development version
uv run --package webtap webtap

# Run tests and checks
make check-webtap   # Check build
make format         # Format code
make lint           # Fix linting
```

## API Server

WebTap automatically starts a FastAPI server on port 8765 for Chrome extension integration:

- `GET /status` - Connection status
- `GET /pages` - List available Chrome pages
- `POST /connect` - Connect to a page
- `POST /disconnect` - Disconnect from current page
- `POST /clear` - Clear events/console/cache
- `GET /fetch/paused` - Get paused requests
- `POST /filters/toggle/{category}` - Toggle filter categories

The API server runs in a background thread and doesn't block the REPL.

## 📄 License

MIT - see [LICENSE](../../LICENSE) for details.