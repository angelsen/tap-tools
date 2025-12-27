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
webtap setup-extension     # Download Chrome extension files
webtap setup-chrome        # Install Chrome wrapper for debugging

# 3. Launch Chrome with debugging
webtap run-chrome          # Or manually: google-chrome-stable --remote-debugging-port=9222

# 4. Start webtap REPL (auto-starts daemon)
webtap

# 5. Connect and explore
>>> pages()                              # List Chrome pages with target IDs
>>> connect("9222:f8134d")               # Connect by target from pages()
>>> network()                            # View network requests (filtered)
>>> network(url="*api*")                 # Filter by URL pattern
>>> request(123, ["response.content"])   # Get response body by row ID
```

## 🔌 MCP Setup for Claude

```bash
# Quick setup with Claude CLI
claude mcp add webtap -- webtap
```

Or manually configure Claude Desktop (`~/Library/Application Support/Claude/claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "webtap": {
      "command": "webtap"
    }
  }
}
```

MCP mode is auto-detected when stdin is piped (no flags needed).

## 🎮 Usage

### Interactive REPL
```bash
webtap                     # Start REPL (or MCP server when piped)
```

### CLI Commands
```bash
webtap --help              # Show help
webtap --version           # Show version
webtap status              # Daemon and connection status
webtap setup-android -y    # Configure Android debugging
webtap run-chrome          # Launch Chrome with debugging
webtap setup-extension     # Download Chrome extension
webtap setup-chrome        # Install Chrome wrapper script
webtap daemon start|stop|status  # Manage daemon
```

### Commands
```python
>>> pages()                              # List Chrome pages with target IDs
>>> connect("9222:f8")                   # Connect by target from pages()
>>> network()                            # View network requests (filtered)
>>> network(status=404, url="*api*")     # Filter by status and URL
>>> console()                            # View console messages
>>> request(123, ["response.content"])   # Get response body by row ID
>>> request(123, ["*"])                  # Get full HAR entry
>>> js("document.title")                 # Execute JavaScript
```

### Command Reference

| Command | Description |
|---------|------------|
| `pages()` | List Chrome pages with target IDs |
| `connect("9222:f8")` | Connect by target ID from pages() |
| `disconnect()` | Disconnect from current page |
| `navigate(url)` | Navigate to URL |
| `network(status, url, type, method)` | View network requests with filters |
| `console(level, limit)` | View console messages |
| `request(id, fields, expr)` | Get HAR request details with field selection |
| `js(code, await_promise, persist)` | Execute JavaScript |
| `filters(add, remove, enable, disable)` | Manage noise filters |
| `fetch(action, options)` | Control request interception |
| `to_model(id, output, model_name)` | Generate Pydantic models from responses |
| `quicktype(id, output, type_name)` | Generate TypeScript/Go/Rust types |
| `clear(events, console)` | Clear events/console |
| `setup-android` | Configure ADB port forwarding for mobile debugging |

## Core Commands

### Connection & Navigation
```python
pages()                      # List Chrome pages with target IDs
connect("9222:f8")           # Connect by target ID from pages()
disconnect()                 # Disconnect from current page
navigate("https://...")      # Navigate to URL
reload(ignore_cache=False)   # Reload page
back() / forward()           # Navigate history
page()                       # Show current page info
status()                     # Show connection and daemon status
```

### Multi-Target Support

Connect to multiple Chrome instances (desktop + Android) simultaneously:

```python
pages()                      # Shows all pages from all registered ports
connect("9222:f8")           # Connect to desktop Chrome page
connect("9224:24")           # Connect to Android Chrome page
targets()                    # Show connected targets
```

Target IDs use format `{port}:{short-id}`. Filter events with `targets.set(["9222:f8"])`.

### Network Monitoring
```python
network()                              # Filtered network requests (default)
network(show_all=True)                 # Show everything (bypass filters)
network(status=404)                    # Filter by HTTP status
network(method="POST")                 # Filter by HTTP method
network(resource_type="xhr")           # Filter by resource type
network(url="*api*")                   # Filter by URL pattern
network(status=200, url="*graphql*")   # Combine filters
```

### Request Inspection
```python
# Get HAR request details by row ID from network() output
request(123)                           # Minimal view (method, url, status)
request(123, ["*"])                    # Full HAR entry
request(123, ["request.headers.*"])    # Request headers only
request(123, ["response.content"])     # Fetch response body
request(123, ["request.postData", "response.content"])  # Both bodies

# With Python expression evaluation
request(123, ["response.content"], expr="json.loads(data['response']['content']['text'])")
request(123, ["response.content"], expr="BeautifulSoup(data['response']['content']['text'], 'html.parser').title")
```

### Code Generation
```python
# Generate Pydantic models from response bodies
to_model(123, "models/user.py", "User")
to_model(123, "models/user.py", "User", json_path="data[0]")  # Extract nested

# Generate TypeScript/Go/Rust/etc types
quicktype(123, "types/user.ts", "User")
quicktype(123, "api.go", "ApiResponse")
```

### Filter Management
```python
filters()                                           # Show all filter groups
filters(add="myfilter", hide={"urls": ["*ads*"]})  # Create filter group
filters(enable="myfilter")                          # Enable group
filters(disable="myfilter")                         # Disable group
filters(remove="myfilter")                          # Delete group

# Built-in groups: ads, tracking, analytics, telemetry, cdn, fonts, images
```

### Request Interception
```python
fetch("status")                     # Check interception status
fetch("enable")                     # Enable request interception
fetch("enable", {"response": True}) # Intercept responses too
fetch("disable")                    # Disable interception
requests()                          # Show paused requests
resume(123)                         # Continue paused request
resume(123, modifications={"url": "..."})  # Modify and continue
fail(123)                           # Block the request
```

### Console & JavaScript
```python
console()                           # View console messages
console(level="error")              # Filter by level
js("document.title")                # Evaluate JavaScript (returns value)
js("fetch('/api').then(r=>r.json())", await_promise=True)  # Async operations
js("var x = 1; x + 1", persist=True)  # Multi-statement (global scope)
js("element.offsetWidth", selection=1)  # Use browser-selected element
clear()                             # Clear events (default)
clear(console=True)                 # Clear browser console
clear(events=True, console=True)    # Clear everything
```

## Architecture

### Daemon-Based Architecture

```
REPL / MCP Client (webtap)
    ↓ JSON-RPC 2.0 (localhost:37650/rpc)
WebTap Daemon (background process)
    ├── FastAPI Server + RPCFramework
    │   └── Single /rpc endpoint (22 methods)
    ├── ConnectionMachine (state lifecycle)
    ↓
Service Layer (WebTapService)
    ├── NetworkService - Request filtering
    ├── ConsoleService - Message handling
    ├── FetchService - Request interception
    └── DOMService - Element selection
    ↓
CDPSession + DuckDB
    ├── events table (method-indexed)
    └── HAR views (pre-aggregated)
    ↓ WebSocket
Chrome Browser (--remote-debugging-port=9222)
```

### How It Works

1. **Daemon manages CDP** - Background process holds WebSocket connection
2. **Events stored as-is** - No transformation, full CDP data preserved in DuckDB
3. **HAR views pre-aggregated** - Network requests correlated for fast querying
4. **Method-indexed events** - O(1) filtering by CDP event type
5. **On-demand body fetching** - Response bodies fetched only when requested
6. **Clients are stateless** - REPL/MCP communicate via HTTP to daemon

## Advanced Usage

### Daemon Management
```bash
webtap daemon start      # Start daemon explicitly
webtap daemon status     # Show daemon status (PID, connections, events)
webtap daemon stop       # Stop running daemon
webtap status            # Quick status check
```

### Expression Evaluation
The `request()` command supports Python expressions with pre-imported libraries:
```python
# Libraries available: json, re, bs4/BeautifulSoup, lxml, jwt, yaml, httpx, etc.
request(123, ["response.content"], expr="json.loads(data['response']['content']['text'])")
request(123, ["response.content"], expr="BeautifulSoup(data['response']['content']['text'], 'html.parser').find_all('a')")
request(123, ["response.content"], expr="jwt.decode(data['response']['content']['text'], options={'verify_signature': False})")
```

### Browser Element Selection
Use the Chrome extension to select DOM elements, then access them:
```python
selections()                                    # View all selected elements
selections(expr="data['selections']['1']")     # Get element #1 data
js("element.offsetWidth", selection=1)          # Run JS on selected element
```

### Direct CDP Commands via JavaScript
```python
# Execute any CDP operation via js()
js("await fetch('/api/data').then(r => r.json())", await_promise=True)
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

| Target      | Title                | URL                            | Connected |
|:------------|:---------------------|:-------------------------------|:----------|
| 9222:dc8f3a | Messenger            | https://www.m...1743198803269/ | No        |
| 9222:dd4b2c | GitHub - replkit2    | https://githu...elsen/replkit2 | No        |
| 9222:f83e1d | YouTube Music        | https://music.youtube.com/     | No        |

_3 pages available_

>>> connect("9222:dd4b2c")
## Connection Established

**Page:** GitHub - angelsen/replkit2
**URL:** https://github.com/angelsen/replkit2
```

### Monitor Network Traffic
```python
>>> network()
## Network Requests

| ID   | Method | Status | URL                                             | Type     | Size |
|:-----|:-------|:-------|:------------------------------------------------|:---------|:-----|
| 3264 | GET    | 200    | https://api.github.com/graphql                  | Fetch    | 22KB |
| 2315 | GET    | 200    | https://api.github.com/repos/angelsen/replkit2  | Fetch    | 16KB |
| 359  | GET    | 200    | https://github.githubassets.com/assets/app.js   | Script   | 21KB |

_3 requests_

>>> # Filter by URL pattern
>>> network(url="*api*")

>>> # Filter by status code
>>> network(status=404)

>>> # Combine filters
>>> network(method="POST", url="*graphql*")
```

### Inspect Request Details
```python
>>> # Get response body
>>> request(3264, ["response.content"])

>>> # Parse JSON response
>>> request(3264, ["response.content"], expr="json.loads(data['response']['content']['text'])")
{'viewer': {'login': 'octocat', 'name': 'The Octocat'}}

>>> # Get full HAR entry
>>> request(3264, ["*"])

>>> # Get just headers
>>> request(3264, ["request.headers.*", "response.headers.*"])
```

### Generate Types from API Responses
```python
>>> # Generate Pydantic model
>>> to_model(3264, "models/github_response.py", "GitHubResponse")
Model written to models/github_response.py

>>> # Generate TypeScript types
>>> quicktype(3264, "types/github.ts", "GitHubResponse")
Types written to types/github.ts
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

>>> # Filter by level
>>> console(level="error")
```

### Intercept and Modify Requests
```python
>>> fetch("enable")
## Fetch Interception Enabled

>>> # Make a request in the browser - it will pause
>>> requests()
## Paused Requests

| ID  | Stage   | Method | URL                    |
|:----|:--------|:-------|:-----------------------|
| 47  | Request | GET    | https://api.example.com|

>>> # Resume normally
>>> resume(47)

>>> # Or modify the request
>>> resume(47, modifications={"url": "https://api.example.com/v2"})

>>> # Or block it
>>> fail(47)
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
3. **Daemon Architecture** - Background process manages CDP connection
4. **HAR-First** - Pre-aggregated views for fast network queries
5. **Minimal Memory** - Store only CDP data

## Requirements

- Chrome/Chromium with debugging enabled (`--remote-debugging-port=9222`)
- Python 3.12+
- Dependencies: websocket-client, duckdb, replkit2, fastapi, uvicorn, beautifulsoup4

## 📚 Documentation

- [Vision](src/webtap/VISION.md) - Design philosophy
- [CDP Module](src/webtap/cdp/README.md) - CDP integration details
- [Commands Guide](src/webtap/commands/DEVELOPER_GUIDE.md) - Command development
- [Tips](src/webtap/commands/TIPS.md) - Command documentation and examples

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
make check         # Type check
make format        # Format code
make lint          # Fix linting
```

## Daemon & API

```bash
webtap daemon start|stop|status
```

Daemon uses ports 37650-37659 (auto-discovery). See [ARCHITECTURE.md](ARCHITECTURE.md) for implementation details.

## 📄 License

MIT - see [LICENSE](../../LICENSE) for details.