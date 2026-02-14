# webtap

Browser debugging via Chrome DevTools Protocol with native event storage, browser-level multiplexing, and declarative target watching.

## Features

- **Browser-Level Multiplexing** - Single WebSocket per Chrome port, multiple sessions
- **Watch Model** - Declarative watch/unwatch with auto-reattach on navigation, reload, SW restart
- **Native CDP Storage** - Events stored exactly as received in DuckDB per target
- **Auto-Watch Children** - Popups and new tabs opened by watched targets are automatically watched
- **Smart Filtering** - Built-in filters for ads, tracking, analytics noise
- **MCP Ready** - Tools and resources for Claude/LLMs
- **Expression Evaluation** - Pre-imported Python libraries for data extraction

## Prerequisites

Chrome or Chromium with DevTools Protocol support:

```bash
# macOS
brew install --cask google-chrome

# Arch Linux
yay -S google-chrome

# Ubuntu/Debian
sudo apt install google-chrome-stable
```

## Installation

```bash
# Install via uv tool (recommended)
uv tool install webtap-tool

# Or with pipx
pipx install webtap-tool

# Update to latest
uv tool upgrade webtap-tool
```

## Quick Start

```bash
# 1. Install webtap
uv tool install webtap-tool

# 2. Optional: Setup helpers (first time only)
webtap setup-browser       # Install browser wrapper for debugging
webtap install-extension   # Install Chrome extension

# 3. Launch Chrome with debugging
webtap run-browser         # Or manually: google-chrome --remote-debugging-port=9222

# 4. Start webtap REPL (auto-starts daemon)
webtap

# 5. Watch and explore
>>> targets()                                          # List Chrome targets
>>> watch(["9222:abc123"])                             # Watch by target ID
>>> network()                                          # View network requests
>>> network(url="*api*")                               # Filter by URL pattern
>>> request(42, "9222:abc123", ["response.content"])   # Get response body
```

## MCP Setup for Claude

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

## Usage

### Interactive REPL
```bash
webtap                     # Start REPL (or MCP server when piped)
```

### CLI Commands
```bash
webtap --help              # Show help
webtap --version           # Show version
webtap status              # Daemon and connection status
webtap run-browser         # Launch Chrome/Edge with debugging
webtap setup-browser       # Install browser wrapper script
webtap install-extension   # Install Chrome extension
webtap setup-android -y    # Configure Android debugging
webtap daemon start|stop|status  # Manage daemon
```

### Command Reference

| Command | Description |
|---------|------------|
| `targets()` | List all Chrome targets (pages, SWs, workers) |
| `watch(["9222:abc"])` | Watch targets — auto-attaches and enables CDP |
| `watching()` | Show currently watched targets with state |
| `unwatch()` | Unwatch all targets |
| `navigate(url, target)` | Navigate target to URL |
| `network(status, url, ...)` | View network requests with filters |
| `console(level, limit)` | View console messages |
| `request(id, target, fields, expr)` | Get HAR request details with field selection |
| `entry(id, target, fields, expr)` | Get console entry details |
| `js(code, target, ...)` | Execute JavaScript |
| `filters(add, remove, ...)` | Manage noise filters |
| `fetch(rules)` | Control request interception and body capture |
| `to_model(id, output, name, target)` | Generate Pydantic models from responses |
| `quicktype(id, output, name, target)` | Generate TypeScript/Go/Rust types |
| `selections()` | View browser-selected elements |
| `clear(events, console)` | Clear events/console |

## Core Commands

### Target Discovery & Watching
```python
targets()                        # List all Chrome targets
watch(["9222:abc123"])           # Watch targets by ID (auto-attaches)
watching()                       # Show watched targets with state
unwatch(["9222:abc123"])         # Unwatch specific target
unwatch()                        # Unwatch all
navigate("https://...", "9222:abc123")  # Navigate to URL
reload("9222:abc123")            # Reload page
back("9222:abc123")              # Go back
```

### Multi-Target Support

Watch multiple targets across Chrome instances simultaneously:

```python
targets()                        # Shows all targets from all registered ports
watch(["9222:abc123"])           # Watch desktop Chrome page
watch(["9224:def456"])           # Watch Android Chrome page
watching()                       # Show all watched targets
```

Target IDs use format `{port}:{short-id}`. Child tabs opened by watched targets are automatically watched.

### Network Monitoring
```python
network()                              # Filtered network requests (default)
network(show_all=True)                 # Show everything (bypass filters)
network(status=404)                    # Filter by HTTP status
network(method="POST")                 # Filter by HTTP method
network(resource_type="xhr")           # Filter by resource type
network(url="*api*")                   # Filter by URL pattern
network(target="9222:abc123")          # Filter to specific target
```

### Request Inspection
```python
# Get HAR request details by row ID and target from network() output
request(42, "9222:abc123")                           # Minimal view
request(42, "9222:abc123", ["*"])                    # Full HAR entry
request(42, "9222:abc123", ["request.headers.*"])    # Request headers only
request(42, "9222:abc123", ["response.content"])     # Fetch response body (auto-decoded from base64)
request(42, "9222:abc123", ["request.postData", "response.content"])  # Both bodies

# With Python expression evaluation
request(42, "9222:abc123", ["response.content"], expr="json.loads(data['response']['content']['text'])")
request(42, "9222:abc123", ["response.content"], expr="BeautifulSoup(data['response']['content']['text'], 'html.parser').title")
```

### Code Generation
```python
# Generate Pydantic models from response bodies
to_model(42, "models/user.py", "User", "9222:abc123")
to_model(42, "models/user.py", "User", "9222:abc123", json_path="data[0]")

# Generate TypeScript/Go/Rust/etc types
quicktype(42, "types/user.ts", "User", "9222:abc123")
quicktype(42, "api.go", "ApiResponse", "9222:abc123")
```

### Filter Management
```python
filters()                                           # Show all filter groups
filters(add="myfilter", hide={"urls": ["*ads*"]})  # Create filter group
filters(enable="myfilter")                          # Enable group
filters(disable="myfilter")                         # Disable group
filters(remove="myfilter")                          # Delete group
```

### Request Interception
```python
fetch()                                    # Show capture state + rules
fetch({"capture": False})                  # Disable body capture
fetch({"mock": {"*api*": '{"ok":1}'}, "target": "9222:abc123"})  # Mock
fetch({"block": ["*tracking*"], "target": "9222:abc123"})        # Block
```

### Console & JavaScript
```python
console()                           # View console messages
console(level="error")              # Filter by level
entry(5, "9222:abc123", ["*"])      # Console entry details

js("document.title", "9222:abc123")                # Evaluate JavaScript
js("fetch('/api').then(r=>r.json())", "9222:abc123", await_promise=True)
js("var x = 1; x + 1", "9222:abc123", persist=True)  # Global scope
js("element.offsetWidth", "9222:abc123", selection=1)  # Selected element

clear()                             # Clear events
clear(events=True, console=True)    # Clear everything
```

## Architecture

### Daemon with Browser-Level Multiplexing

```
REPL / MCP Client (webtap)
    | JSON-RPC 2.0 (localhost:37650/rpc)
WebTap Daemon (background process)
    +-- FastAPI Server + RPCFramework
    +-- BrowserSession (one WebSocket per Chrome port)
    |       +-- CDPSession (per target, DuckDB storage)
    |       +-- CDPSession (per target, DuckDB storage)
    +-- ConnectionManager (per-target state)
    |
Service Layer (WebTapService)
    +-- NetworkService - Request queries via HAR views
    +-- ConsoleService - Message handling
    +-- FetchService - Request interception + body capture
    +-- DOMService - Element selection
```

### How It Works

1. **Browser-level WebSocket** - One connection per Chrome port, multiplexed sessions
2. **Watch model** - Targets auto-reattach on navigation, reload, SW restart
3. **Events stored as-is** - No transformation, full CDP data preserved in DuckDB
4. **HAR views pre-aggregated** - Network requests correlated for fast querying
5. **Base64 auto-decoded** - Response bodies decoded to UTF-8; binary stays base64
6. **On-demand body fetching** - Response bodies fetched only when requested
7. **Auto-watch children** - Popups/new tabs from watched targets are automatically watched

## Examples

### Watch Targets and Monitor Traffic
```python
>>> targets()
## Targets

| Target      | Type | Title           | URL                              | State   |
|:------------|:-----|:----------------|:---------------------------------|:--------|
| 9222:abc123 | page | GitHub          | https://github.com/angelsen      |         |
| 9222:def456 | page | YouTube Music   | https://music.youtube.com/       |         |

>>> watch(["9222:abc123"])
## Watching

| Target      | State    | Title  | URL                         |
|:------------|:---------|:-------|:----------------------------|
| 9222:abc123 | attached | GitHub | https://github.com/angelsen |
```

### Inspect Network Requests
```python
>>> network(url="*api*")
## Network Requests

| ID   | Target      | Method | Status | URL                            | Type  | Size |
|:-----|:------------|:-------|:-------|:-------------------------------|:------|:-----|
| 42   | 9222:abc123 | GET    | 200    | https://api.github.com/graphql | Fetch | 22KB |

>>> request(42, "9222:abc123", ["response.content"], expr="json.loads(data['response']['content']['text'])")
{'viewer': {'login': 'octocat', 'name': 'The Octocat'}}
```

### Generate Types from API Responses
```python
>>> to_model(42, "models/github.py", "GitHubResponse", "9222:abc123")
Model written to models/github.py

>>> quicktype(42, "types/github.ts", "GitHubResponse", "9222:abc123")
Types written to types/github.ts
```

## Advanced Usage

### Expression Evaluation
The `request()` command supports Python expressions with pre-imported libraries:
```python
# Libraries: json, re, bs4/BeautifulSoup, lxml, jwt, yaml, httpx, urllib, datetime
request(42, "9222:abc123", ["response.content"], expr="json.loads(data['response']['content']['text'])")
request(42, "9222:abc123", ["response.content"], expr="BeautifulSoup(data['response']['content']['text'], 'html.parser').find_all('a')")
```

### Browser Element Selection
Use the Chrome extension to select DOM elements, then access them:
```python
selections()                                    # View all selected elements
selections(expr="data['selections']['1']")     # Get element #1 data
js("element.offsetWidth", "9222:abc123", selection=1)  # JS on selected element
```

### Chrome Extension

Install the extension:
```bash
webtap install-extension   # Installs to platform data directory
```
Then load as unpacked extension in `chrome://extensions/` with Developer mode enabled.

## Design Principles

1. **Store AS-IS** - No transformation of CDP events
2. **Query On-Demand** - Extract only what's needed
3. **Watch Model** - Declarative target management with auto-reattach
4. **Browser-Level Multiplexing** - Single WebSocket per port
5. **HAR-First** - Pre-aggregated views for fast network queries

## Requirements

- Chrome/Chromium with debugging enabled (`--remote-debugging-port=9222`)
- Python 3.12+
- Dependencies: websocket-client, duckdb, replkit2, fastapi, uvicorn, beautifulsoup4

## Documentation

- [Vision](src/webtap/VISION.md) - Design philosophy
- [Architecture](ARCHITECTURE.md) - Implementation guide
- [Tips](src/webtap/commands/TIPS.md) - Command documentation and examples

## Development

```bash
git clone https://github.com/angelsen/tap-tools
cd tap-tools
uv sync --package webtap
uv run --package webtap webtap

make check         # Type check
make format        # Format code
make lint          # Fix linting
```

Daemon uses ports 37650-37659 (auto-discovery). See [ARCHITECTURE.md](ARCHITECTURE.md) for details.

## License

MIT - see [LICENSE](../../LICENSE) for details.
