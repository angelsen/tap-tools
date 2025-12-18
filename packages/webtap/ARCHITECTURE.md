# WebTap Architecture

Implementation guide for WebTap's RPC-based daemon architecture.

## Core Components

### RPCFramework (rpc/framework.py)
- JSON-RPC 2.0 request/response handler
- State validation via `requires_state` decorator
- Epoch tracking for stale request detection
- Thread-safe execution via `asyncio.to_thread()`

### ConnectionMachine (rpc/machine.py)
- Thread-safe state machine using `transitions.LockedMachine`
- States: `disconnected` → `connecting` → `connected` → `inspecting`
- Epoch incremented on successful connection

### RPCClient (client.py)
- Single `call(method, **params)` interface
- Automatic epoch synchronization
- `RPCError` exception for structured errors

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

def connect(ctx: RPCContext, page: int = None, page_id: str = None) -> dict:
    """Connect to Chrome page - manages state transitions."""
    # Validate params
    if page is None and page_id is None:
        raise RPCError(ErrorCode.INVALID_PARAMS, "Must specify page or page_id")

    # State transition
    ctx.machine.start_connect()
    try:
        result = ctx.service.connect_to_page(page_index=page, page_id=page_id)
        ctx.machine.connect_success()  # Increments epoch
        return {"connected": True, **result}
    except Exception as e:
        ctx.machine.connect_failed()
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

## State Machine

```
                    ┌─────────────────┐
                    │  disconnected   │ ←─────────────────┐
                    └────────┬────────┘                   │
                             │ start_connect              │
                    ┌────────▼────────┐                   │
                    │   connecting    │──connect_failed───┘
                    └────────┬────────┘
                             │ connect_success (epoch++)
                    ┌────────▼────────┐
           ┌───────→│    connected    │←───────┐
           │        └────────┬────────┘        │
           │                 │ start_inspect   │ stop_inspect
           │        ┌────────▼────────┐        │
           │        │   inspecting    │────────┘
           │        └────────┬────────┘
           │                 │ start_disconnect
           │        ┌────────▼────────┐
           └────────│  disconnecting  │
                    └─────────────────┘
```

## Epoch Tracking

Prevents stale requests after reconnection:

1. Client sends `epoch` with requests (after first sync)
2. Server validates epoch matches current state
3. Stale requests rejected with `STALE_EPOCH` error
4. Epoch incremented only on `connect_success`

## File Structure

```
rpc/
├── __init__.py      # Exports: RPCFramework, RPCError, ErrorCode, ConnectionState
├── framework.py     # RPCFramework, RPCContext, HandlerMeta
├── handlers.py      # 22 RPC method handlers
├── machine.py       # ConnectionMachine, ConnectionState
└── errors.py        # ErrorCode, RPCError
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
