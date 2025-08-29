# WebTap Architecture

Implementation guide for WebTap commands following the VISION.

## Core Components

### CDPSession (cdp/session.py)
- WebSocket connection to Chrome
- DuckDB in-memory storage: `CREATE TABLE events (event JSON)`
- Events stored AS-IS: `INSERT INTO events VALUES (?)`
- Query interface: `query(sql)` - returns result rows
- Body fetching: `fetch_body(request_id)` - CDP call on-demand

### Command Pattern

Commands query DuckDB and return data for Replkit2 display.

```python
@app.command
def network(state, query: dict = None):
    """Query network events with flexible filtering."""
    
    # Default query
    default = {
        'limit': 20,
        'exclude_static': True,  # Skip images/fonts
        'exclude_tracking': True  # Skip analytics
    }
    q = {**default, **(query or {})}
    
    # Build SQL from query dict
    sql = build_network_sql(q)
    
    # Return for Replkit2 display
    return state.cdp.query(sql)
```

## Command Implementation Guide

### network(query: dict)
```python
# Query dict can contain:
# - id: Single request detail
# - status: Filter by status code
# - method: Filter by HTTP method
# - url_contains: Substring match
# - limit: Result limit
# - exclude_static: Hide images/css/fonts
# - exclude_tracking: Hide analytics

# Build SQL:
SELECT 
    json_extract_string(event, '$.params.requestId') as id,
    json_extract_string(event, '$.params.response.status') as status,
    json_extract_string(event, '$.params.response.url') as url
FROM events
WHERE json_extract_string(event, '$.method') = 'Network.responseReceived'
    AND [additional filters from query dict]
LIMIT 20
```

### console(query: dict)
```python
# Query dict can contain:
# - level: 'error', 'warn', 'log'
# - source: 'console', 'network', 'security'
# - contains: Text search in message
# - limit: Result limit

# Build SQL:
SELECT 
    json_extract_string(event, '$.params.type') as level,
    json_extract_string(event, '$.params.args[0].value') as message,
    json_extract_string(event, '$.params.timestamp') as time
FROM events
WHERE json_extract_string(event, '$.method') IN ('Runtime.consoleAPICalled', 'Log.entryAdded')
    AND [additional filters]
```

### body(id: str, expr: str = None)
```python
# Fetch body on-demand
result = state.cdp.fetch_body(id)

if not expr:
    return result['body']  # Raw body

# Evaluate Python expression on body (like inspect command)
context = {
    'data': result['body'],
    'json': json.loads(result['body']) if parseable,
    're': __import__('re')
}
return eval(expr, {}, context)
```

### inspect(query: dict, expr: str)
```python
# Query events then apply Python expression
events = state.cdp.query(build_sql(query))

# Apply expression to each event
results = []
for event in events:
    context = {'event': json.loads(event[0])}
    results.append(eval(expr, {}, context))
return results
```

## SQL Patterns

### Fuzzy field matching
```sql
-- Find any field containing 'status'
SELECT * FROM events 
WHERE json_extract_string(event, '$.params.response.status') = '404'
   OR json_extract_string(event, '$.params.status') = '404'
```

### Correlation by requestId
```sql
-- Get all events for a request
SELECT event FROM events
WHERE json_extract_string(event, '$.params.requestId') = ?
ORDER BY rowid
```

### Exclude noise
```sql
-- Skip tracking/analytics
WHERE json_extract_string(event, '$.params.request.url') NOT LIKE '%google-analytics%'
  AND json_extract_string(event, '$.params.request.url') NOT LIKE '%doubleclick%'
  AND json_extract_string(event, '$.params.type') NOT IN ('Image', 'Font', 'Stylesheet')
```

## Display Strategy

- **Lists**: Return list of dicts for Replkit2 table display
- **Details**: Return single dict for box display
- **Raw**: Return JSON strings for inspect/debug

Commands should NOT format output - let Replkit2 handle display based on `@app.command(display="table"|"markdown"|"raw")`.

## Future Commands

- `storage()` - Query cookies/localStorage via CDP
- `api()` - Discover API endpoints from traffic
- `har()` - Export to HAR format
- `intercept()` - Modify requests (requires Fetch domain)
- `timeline()` - Request/response correlation view