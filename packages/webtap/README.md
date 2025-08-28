# WebTap

Chrome DevTools Protocol REPL for browser debugging and automation.

## Overview

WebTap provides a clean, minimal interface to Chrome's debugging protocol. It stores CDP events as-is, builds summaries only for display, and queries additional data on-demand.

## Installation

```bash
# Install with uv
uv tool install webtap

# Or install from source
cd packages/webtap
uv sync
```

## Quick Start

1. **Start Chrome with debugging enabled:**
```bash
# macOS
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222

# Linux
google-chrome --remote-debugging-port=9222

# Windows
chrome.exe --remote-debugging-port=9222
```

2. **Run WebTap:**
```bash
webtap
```

3. **Connect and use:**
```python
>>> pages()  # List available tabs
>>> connect(0)  # Connect to first tab
>>> network()  # View network requests
>>> console()  # View console messages
```

## Core Commands

### Connection
- `pages()` - List available Chrome tabs
- `connect(page)` - Connect to a tab and enable all CDP domains
- `disconnect()` - Disconnect from Chrome
- `status()` - Show connection status

### Navigation
- `navigate(url)` - Go to URL
- `reload(ignore_cache=False)` - Reload page
- `back()` / `forward()` - Navigate history
- `page()` - Current page information
- `history()` - Navigation history

### Monitoring
- `network(id=None, body=False, limit=20)` - Network requests
- `console(id=None, limit=20)` - Console messages
- `clear_console()` - Clear console events

### Execution
- `eval(expression, await_promise=False)` - Evaluate JavaScript
- `exec(expression)` - Execute JavaScript without return

## Architecture

WebTap follows a "work WITH CDP" philosophy:

```
Chrome → WebSocket → CDP Events (stored as-is) → Helpers → Display
                           ↓
                    On-demand queries (bodies, cookies, etc.)
```

### Key Principles

1. **Store CDP events as-is** - No transformation, full fidelity
2. **Minimal summaries** - Extract only what's needed for tables
3. **Query on-demand** - Fetch bodies, cookies when requested
4. **No abstractions** - Direct CDP access via `send()` and `execute()`

### Display Strategy

- **Tables** - Lists of items (pages, requests, messages)
- **Markdown** - Status and info displays
- **Raw** - CDP responses and detail views

## Examples

### Monitor Network Traffic
```python
>>> connect(0)
Connected to: Example Site
https://example.com

>>> network()
ID          Method  Status  URL                                                 Type        Size
----------  ------  ------  --------------------------------------------------  ----------  ------
336990.332  GET     200     https://github.githubassets.com/...882e354c005.png  Other       -
336990.331  GET     200     https://github.com/manifest.json                    Manifest    -
336990.330  POST    204     https://collector.github.com/github/collect         Ping        456

>>> network(id="1234", body=True)  # Get details with body
{'id': '1234...', 'status': 200, 'body': '<html>...', ...}
```

### Execute JavaScript
```python
>>> eval("document.title")
'Example Domain'

>>> eval("[1,2,3].map(x => x * 2)")
[2, 4, 6]

>>> exec("console.log('Hello from WebTap')")
{'executed': True}

>>> console()
Time              Level       Message                                                                              Source
----------------  ----------  -----------------------------------------------------------------------------------  --------
1756388168328.89  WARNING     An iframe which has both allow-scripts and allow-same-origin for its sandbox att...  security
1756388167996.90  WARNING     An iframe which has both allow-scripts and allow-same-origin for its sandbox att...  security
1756388167984.58  ENDGROUP    console.groupEnd                                                                     console

```

### Navigate and Monitor
```python
>>> navigate("https://httpbin.org/json")
{'frameId': '...', 'loaderId': '...'}

>>> network(limit=5)  # See recent requests
>>> console()  # Check for errors
```

## Advanced Usage

### Direct CDP Access

WebTap provides direct access to CDP for advanced use:

```python
# Async command - returns Future
future = state.cdp.send("Network.getResponseBody", {"requestId": "..."})
body = future.result(timeout=5)

# Sync command - blocks until response
result = state.cdp.execute("Page.captureScreenshot", {"format": "png"})
```

### Event Access

All CDP events are stored as-is and accessible:

```python
# Network events grouped by requestId
state.cdp.network_events  # dict[str, list[dict]]

# Console events in chronological order  
state.cdp.console_events  # deque[dict]
```

## Design Philosophy

WebTap is intentionally minimal:

- **No abstractions** over CDP - use it directly
- **No transformations** - CDP events stored as-is
- **No auto-enable** - explicit domain enabling
- **No convenience methods** - just `send()` and `execute()`
- **No formatters** - Replkit2 handles display

This design makes WebTap:
- **Transparent** - See exactly what CDP sends
- **Debuggable** - Raw events available
- **Extensible** - Direct CDP access for anything
- **Maintainable** - Minimal code, clear separation

## Requirements

- Chrome/Chromium with remote debugging enabled
- Python 3.12+
- `websocket-client` for WebSocket communication
- `replkit2` for REPL interface

## Development

```bash
# Clone repository
git clone https://github.com/yourusername/tap-tools
cd tap-tools/packages/webtap

# Install for development
uv sync

# Run development version
uv run webtap

# Format, typechecking and lint
ruff format packages/webtap/src/webtap
ruff check --fix packages/webtap/src/webtap
basedpyright packages/webtap/src/webtap
```

## License

MIT - See [LICENSE](../../LICENSE) for details.