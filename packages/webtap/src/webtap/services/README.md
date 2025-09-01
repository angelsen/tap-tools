# WebTap Services Layer

The services layer provides clean, reusable interfaces for querying and managing CDP events stored in DuckDB.

## Architecture

```
commands/ → services/ → cdp/session → DuckDB
    ↓          ↓
   API    Properties/Methods
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
Manages HTTP request/response interception.

**Key Properties:**
- `paused_count` - Number of paused requests

**Key Methods:**
- `get_paused_rowids()` - List of paused request rowids
- `enable()` / `disable()` - Control interception
- `continue_request()` / `fail_request()` - Process paused requests

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

Services are accessed through the WebTapState:

```python
# In commands
@app.command()
def network(state):
    results = state.service.network.get_recent_requests(limit=20)
    count = state.service.network.request_count
    
# In API
@api.get("/status")
async def status():
    return app_state.service.get_status()
```