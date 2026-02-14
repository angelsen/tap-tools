# WebTap Architecture

Implementation guide for WebTap's browser-level multiplexing and watch-based connection model.

## Core Components

### BrowserSession (cdp/browser.py)
- Single WebSocket per Chrome port connecting to `/devtools/browser/<id>`
- Manages multiple `CDPSession` instances via `Target.attachToTarget` with `flatten: True`
- Routes CDP events to correct session by `sessionId`
- Handles browser-level events: `Target.targetCreated`, `Target.targetDestroyed`, `Target.targetInfoChanged`, `Target.detachedFromTarget`
- Maintains thread-safe watched target/URL sets with dual-key lookup (target ID + URL)
- Opener-based auto-attach: child tabs of watched targets are automatically watched

### CDPSession (cdp/session.py)
- Delegates `send()`/`execute()` to `BrowserSession` (does not own a WebSocket)
- Stores events in DuckDB with HAR view aggregation
- Tracks `target_info` and `chrome_target_id` for lifecycle matching
- `is_connected` checks browser session + session registration

### RPCFramework (rpc/framework.py)
- JSON-RPC 2.0 request/response handler
- State validation via `requires_state` parameter
- Epoch tracking for stale request detection (skipped for read-only handlers)
- Thread-safe execution via `asyncio.to_thread()`

### ConnectionManager (services/connection.py)
- Thread-safe per-target connection lifecycle management
- States: `CONNECTING` → `ATTACHED` → `SUSPENDED` (SW idle-stop)
- `inspecting` is a boolean flag on connections (not a separate state)
- `auto_attached` flag for opener-matched popup targets
- Epoch incremented on any state change

### RPCClient (client.py)
- Single `call(method, **params)` interface
- Automatic epoch synchronization
- Auto-retries `STALE_EPOCH` errors

## Watch/Unwatch Model

Declarative target management replaces imperative connect/disconnect:

```
watch(["9222:abc123"])     # Start watching target (auto-attaches)
unwatch(["9222:abc123"])   # Stop watching target
unwatch()                  # Unwatch all
```

Watched targets auto-reattach when they:
- Navigate to a new URL
- Reload the page
- Restart after service worker idle-stop
- Appear as child tabs (opener matching)

### Auto-Watch Propagation

When a watched tab opens a child (popup, new tab), the child is auto-attached and added to the watched set. This propagates recursively:

```
Watched tab opens popup  →  popup auto-attached + added to watched set
  popup opens print page →  print page auto-attached (grandchild)
```

### Stashed DuckDBs

When a URL-watched target disconnects (e.g., service worker idle-stop), its DuckDB is stashed. History remains queryable via `get_query_cdps()` which returns active CDPs + stashed DBs.

## Browser-Level Multiplexing

Single WebSocket per Chrome port, multiple sessions:

```
┌─────────────────────────────────┐
│ Chrome :9222                    │
│  ├─ page abc123 (watched)       │
│  ├─ page def456 (auto-attached) │
│  └─ SW xyz789 (watched by URL)  │
└────────────┬────────────────────┘
             │ Single WebSocket to /devtools/browser/<id>
┌────────────▼────────────────────┐
│ BrowserSession (port 9222)      │
│  ├─ CDPSession (abc123)         │
│  ├─ CDPSession (def456)         │
│  └─ CDPSession (xyz789)         │
└────────────┬────────────────────┘
             │
┌────────────▼────────────────────┐
│ WebTapService                   │
│  ├─ ConnectionManager           │
│  ├─ NetworkService              │
│  ├─ ConsoleService              │
│  ├─ FetchService                │
│  └─ DOMService                  │
└─────────────────────────────────┘
```

**Target ID format:** `{port}:{6-char-short-id}` (e.g., `9222:abc123`)

## Daemon Lifecycle

- **Port discovery:** Scans 37650-37659, writes to `~/.local/state/webtap/daemon.port`
- **Version check:** Health endpoint returns version; clients auto-restart outdated daemons
- **Browser registration:** `ports.add(port)` creates `BrowserSession`, discovers targets

## Request Flow

```
Command Layer           RPC Layer              Service Layer
─────────────────────────────────────────────────────────────
network(state)    →  client.call("network")  →  RPCFramework.handle()
                                                      ↓
                                             handlers.network(ctx)
                                                      ↓
                                             ctx.service.network.get_requests()
                                                      ↓
                                             DuckDB query (active + stashed)
```

## RPC Handler Pattern

Handlers in `rpc/handlers.py` are thin wrappers:

```python
def targets(ctx: RPCContext) -> dict:
    """List all discoverable targets across all browsers."""
    return {"targets": ctx.service.list_targets()}

def watch(ctx: RPCContext, targets: list[str]) -> dict:
    """Watch targets by ID - auto-attaches and enables CDP domains."""
    result = ctx.service.watch_targets(targets)
    return result
```

## Handler Registration

```python
def register_handlers(rpc: RPCFramework) -> None:
    rpc.method("targets")(targets)
    rpc.method("watch", broadcasts=True)(watch)
    rpc.method("unwatch", broadcasts=True)(unwatch)
    rpc.method("network")(network)       # Read-only, skips epoch check
    rpc.method("js", requires_state=_ATTACHED_ONLY)(js)
    # ...
```

## Connection States

Per-target state managed by `ConnectionManager`:

```
                    ┌─────────────────┐
                    │   CONNECTING    │
                    └────────┬────────┘
                             │ success (epoch++)
                    ┌────────▼────────┐
                    │    ATTACHED     │ ←── inspecting: bool flag
                    └───┬─────────┬───┘
                        │         │ SW idle-stop
                        │    ┌────▼────────┐
                        │    │  SUSPENDED  │ (stashed DB, auto-resume)
                        │    └──────┬──────┘
                        │           │
                        │ unwatch   │ unwatch
                    ┌───▼───────────▼─┐
                    │  DISCONNECTING  │ (transient: CDP cleanup guard)
                    └────────┬────────┘
                             │ (epoch++)
                    ┌────────▼────────┐
                    │    (removed)    │
                    └─────────────────┘
```

Each target has independent state. Multiple targets can be attached simultaneously.

## Domain Enables by Target Type

```python
_DOMAINS_BY_TYPE = {
    "page":             ["Page", "Network", "Runtime", "Log", "DOMStorage"],
    "service_worker":   ["Network", "Runtime", "Log"],
    "background_page":  ["Network", "Runtime", "Log", "DOMStorage"],
    "worker":           ["Network", "Runtime"],
}
```

## Epoch Tracking

Prevents stale requests after state changes:

1. Client sends `epoch` with requests (after first sync)
2. Server validates epoch for state-mutating handlers (`broadcasts=True`)
3. Read-only handlers skip epoch check
4. Stale requests rejected with `STALE_EPOCH` error; client auto-retries with updated epoch
5. Epoch incremented on watch, unwatch, or inspection state change

## File Structure

```
webtap/
├── targets.py       # Target ID utilities ({port}:{short-id})
├── notices.py       # Multi-surface warning system
├── cdp/
│   ├── browser.py       # BrowserSession (one WS per port, session multiplexing)
│   ├── session.py       # CDPSession (DuckDB storage, event handling)
│   └── har.py           # HAR view aggregation
├── rpc/
│   ├── framework.py     # RPCFramework, RPCContext, HandlerMeta
│   ├── handlers.py      # RPC method handlers
│   └── errors.py        # ErrorCode, RPCError
├── services/
│   ├── main.py          # WebTapService orchestrator
│   ├── connection.py    # ConnectionManager, ActiveConnection, TargetState
│   ├── network.py       # Network event queries using HAR views
│   ├── console.py       # Console message handling
│   ├── fetch.py         # Request interception
│   └── dom.py           # DOM inspection & element selection
└── extension/
    ├── controllers/
    │   ├── targets.js       # Target discovery list with filter
    │   ├── watching.js      # Watched targets with state indicators
    │   ├── capture.js       # Capture state display
    │   ├── network.js       # Network request table
    │   └── console.js       # Console message table
    └── lib/
        ├── target-utils.js  # Shared target display helpers
        └── ui.js            # State icons and UI utilities
```

## Adding New RPC Methods

1. Add handler function in `handlers.py`:
```python
def my_method(ctx: RPCContext, target: str, param: str) -> dict:
    cdp = ctx.service.resolve_cdp(target)
    result = cdp.execute("SomeDomain.method", {"param": param})
    return {"data": result}
```

2. Register in `register_handlers()`:
```python
rpc.method("my_method", requires_state=_ATTACHED_ONLY)(my_method)
```

3. Add command wrapper (optional, for REPL/MCP):
```python
@app.command()
def my_command(state, target: str, param: str):
    result = state.client.call("my_method", target=target, param=param)
    return format_response(result)
```
