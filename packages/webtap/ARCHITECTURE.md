# WebTap Architecture

Implementation guide for WebTap's RPC-based daemon architecture.

## Core Components

### RPCFramework (rpc/framework.py)
- JSON-RPC 2.0 request/response handler
- State validation via `requires_state` decorator
- Epoch tracking for stale request detection
- Thread-safe execution via `asyncio.to_thread()`

### ConnectionManager (services/connection.py)
- Thread-safe per-target connection lifecycle management
- States: `CONNECTING` → `CONNECTED` → `DISCONNECTING`
- `inspecting` is a boolean flag on connections (not a separate state)
- Epoch incremented on any state change

### RPCClient (client.py)
- Single `call(method, **params)` interface
- Automatic epoch synchronization
- `RPCError` exception for structured errors

## Multi-Target Architecture

Simultaneous connections to multiple Chrome instances:

```
┌─────────────────┐     ┌─────────────────┐
│ Chrome :9222    │     │ Chrome :9223    │
│  ├─ page abc123 │     │  ├─ page def456 │
│  └─ page xyz789 │     │  └─ page ghi012 │
└────────┬────────┘     └────────┬────────┘
         │                       │
         └───────┬───────────────┘
                 ▼
         ┌───────────────┐
         │    Daemon     │
         │ cdp_sessions: │
         │  9222: CDPSession
         │  9223: CDPSession
         └───────────────┘
```

**Target ID format:** `{port}:{6-char-short-id}` (e.g., `9222:abc123`)

**Filtering:** `targets.set(["9222:abc123"])` filters events to specific targets.

## Daemon Lifecycle

- **Port discovery:** Scans 37650-37659, writes to `~/.local/state/webtap/daemon.port`
- **Version check:** Health endpoint returns version; clients auto-restart outdated daemons
- **Port management:** `ports.add(port)` validates Chrome availability, creates CDPSession

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
                                             DuckDB query + HAR views
```

## RPC Handler Pattern

Handlers in `rpc/handlers.py` are thin wrappers:

```python
def network(ctx: RPCContext, limit: int = 50, status: int = None) -> dict:
    """Query network requests - delegates to NetworkService."""
    requests = ctx.service.network.get_requests(
        limit=limit,
        status=status,
    )
    return {"requests": requests}

def connect(ctx: RPCContext, target: str) -> dict:
    """Connect to Chrome page by target ID (e.g., "9222:f8134d")."""
    try:
        result = ctx.service.connect_to_page(target=target)
        # ConnectionManager.connect() increments epoch
        return {"connected": True, **result}
    except Exception as e:
        raise RPCError(ErrorCode.NOT_CONNECTED, str(e))
```

## Handler Registration

```python
# In rpc/handlers.py
def register_handlers(rpc: RPCFramework) -> None:
    rpc.method("connect")(connect)
    rpc.method("disconnect", requires_state=["connected", "inspecting"])(disconnect)
    rpc.method("network", requires_state=["connected", "inspecting"])(network)
    rpc.method("js", requires_state=["connected", "inspecting"])(js)
    # ... 22 methods total
```

## Command Layer Pattern

Commands are display wrappers around RPC calls:

```python
@app.command(display="table")
def network(state, limit: int = 50, status: int = None):
    """View network requests."""
    try:
        result = state.client.call("network", limit=limit, status=status)
        return table_response(
            data=result["requests"],
            headers=["ID", "Method", "Status", "URL"],
        )
    except RPCError as e:
        return error_response(e.message)
```

## Connection States

Per-target state managed by `ConnectionManager` (not a global state machine):

```
                    ┌─────────────────┐
                    │   CONNECTING    │
                    └────────┬────────┘
                             │ success (epoch++)
                    ┌────────▼────────┐
                    │    CONNECTED    │ ←── inspecting: bool flag
                    └────────┬────────┘
                             │ disconnect (epoch++)
                    ┌────────▼────────┐
                    │  DISCONNECTING  │
                    └─────────────────┘
```

Each target has independent state. Multiple targets can be connected simultaneously.

## Epoch Tracking

Prevents stale requests after state changes:

1. Client sends `epoch` with requests (after first sync)
2. Server validates epoch matches current state
3. Stale requests rejected with `STALE_EPOCH` error
4. Epoch incremented on connect, disconnect, or inspection state change

## File Structure

```
webtap/
├── targets.py       # Target ID utilities ({port}:{short-id})
├── notices.py       # Multi-surface warning system
├── rpc/
│   ├── __init__.py      # Exports: RPCFramework, RPCError, ErrorCode
│   ├── framework.py     # RPCFramework, RPCContext, HandlerMeta
│   ├── handlers.py      # 22+ RPC method handlers
│   └── errors.py        # ErrorCode, RPCError
├── services/
│   └── connection.py    # ConnectionManager, ActiveConnection, TargetState
```

## Adding New RPC Methods

1. Add handler function in `handlers.py`:
```python
def my_method(ctx: RPCContext, param: str) -> dict:
    result = ctx.service.do_something(param)
    return {"data": result}
```

2. Register in `register_handlers()`:
```python
rpc.method("my_method", requires_state=["connected"])(my_method)
```

3. Add command wrapper (optional, for REPL):
```python
@app.command()
def my_command(state, param: str):
    result = state.client.call("my_method", param=param)
    return format_response(result)
```
