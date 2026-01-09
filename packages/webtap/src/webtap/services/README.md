# WebTap Services Layer

The services layer provides clean, reusable interfaces for querying and managing CDP events stored in DuckDB.

## Architecture

```
commands/ → RPCClient → /rpc endpoint → RPCFramework → services/ → cdp/session → DuckDB
                              ↓
                     rpc/handlers.py (thin wrappers)
```

## Services

### WebTapService (`main.py`)
Main orchestrator that manages all domain-specific services and CDP connection.

**Key Properties:**
- `event_count` - Total CDP events stored

**Key Methods:**
- `connect_to_page()` - Connect and enable CDP domains
- `disconnect()` - Clean disconnection
- `get_status()` - Comprehensive status with metrics from all services

### FetchService (`fetch.py`)
Manages HTTP request/response interception with declarative rules.

**Key Properties:**
- `capture_enabled` - Global capture flag (default: True)
- `capture_count` - Bodies captured this session
- `_target_rules` - Per-target block/mock rules

**Key Methods:**
- `enable_on_target(target, cdp)` - Enable capture on new connection
- `cleanup_target(target, cdp)` - Clean up on disconnect/crash
- `set_capture(enabled)` - Toggle global capture
- `set_rules(target, block, mock)` - Set per-target rules
- `get_status()` - Current capture state and rules

### NetworkService (`network.py`)
Queries network events (requests/responses).

**Key Properties:**
- `request_count` - Total network requests

**Key Methods:**
- `get_recent_requests()` - Network events with filter support
- `get_failed_requests()` - 4xx/5xx errors
- `get_request_by_id()` - All events for a request

### ConsoleService (`console.py`)
Queries console messages and browser logs.

**Key Properties:**
- `message_count` - Total console messages
- `error_count` - Console errors only

**Key Methods:**
- `get_recent_messages()` - Console events with level filter
- `get_errors()` / `get_warnings()` - Filtered queries
- `clear_browser_console()` - CDP command to clear console

## Design Principles

1. **Rowid-Native**: All queries return rowid as primary identifier
2. **Direct Queries**: No caching, query DuckDB on-demand
3. **Properties for Counts**: Common counts exposed as properties
4. **Methods for Queries**: Complex queries as methods with parameters
5. **Service Isolation**: Each service manages its domain independently

## Usage

Services are accessed through the application state:

```python
# In commands (via RPC)
@app.command()
def network(state, limit: int = 50):
    result = state.client.call("network", limit=limit)
    return table_response(result["requests"], ...)

# In RPC handlers (thin wrappers)
def network(ctx: RPCContext, limit: int = 50) -> dict:
    requests = ctx.service.network.get_requests(limit=limit)
    return {"requests": requests}
```