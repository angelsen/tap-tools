# WebTap Command Documentation

## Libraries
All commands have these pre-imported (no imports needed!):
- **Web:** bs4/BeautifulSoup, lxml, ElementTree/ET
- **Data:** json, yaml, msgpack, protobuf_json/protobuf_text
- **Security:** jwt, base64, hashlib, cryptography
- **HTTP:** httpx, urllib
- **Text:** re, difflib, textwrap, html
- **Utils:** datetime, collections, itertools, pprint, ast

## Commands

### body
Fetch and analyze HTTP request or response bodies with Python expressions. Automatically detects event type.

#### Examples
```python
# Response bodies
body(123)                                  # Get response body
body(123, "json.loads(body)")              # Parse JSON response
body(123, "bs4(body, 'html.parser').find('title').text")  # HTML title

# Request bodies (POST/PUT/PATCH)
body(456)                                  # Get request POST data
body(456, "json.loads(body)")              # Parse JSON request body
body(456, "json.loads(body)['customerId']")  # Extract request field

# Analysis
body(123, "jwt.decode(body, options={'verify_signature': False})")  # Decode JWT
body(123, "re.findall(r'/api/[^\"\\s]+', body)[:10]")  # Find API endpoints
body(123, "httpx.get(json.loads(body)['next_url']).json()")  # Chain requests
body(123, "msgpack.unpackb(body)")         # Binary formats
```

#### Tips
- **Auto-detect type:** Command automatically detects request vs response events
- **Find request events:** `events({"method": "Network.requestWillBeSent", "url": "*WsJobCard/Post*"})` - POST requests
- **Generate models:** `to_model({id}, "models/model.py", "Model")` - create Pydantic models from JSON
- **Generate types:** `quicktype({id}, "types.ts", "Type")` - TypeScript/other languages
- **Chain requests:** `body({id}, "httpx.get(json.loads(body)['next_url']).text[:100]")`
- **Parse XML:** `body({id}, "ElementTree.fromstring(body).find('.//title').text")`
- **Extract forms:** `body({id}, "[f['action'] for f in bs4(body, 'html.parser').find_all('form')]")`
- **Decode protobuf:** `body({id}, "protobuf_json.Parse(body, YourMessage())")`
- **Find related:** `events({'requestId': request_id})` - related events

### to_model
Generate Pydantic v2 models from request or response bodies.

#### Examples
```python
# Response bodies
to_model(123, "models/product.py", "Product")                              # Full response
to_model(123, "models/customers/group.py", "CustomerGroup", json_path="data[0]")  # Extract nested

# Request bodies (POST/PUT/PATCH)
to_model(172, "models/form.py", "JobCardForm", expr="dict(urllib.parse.parse_qsl(body))")  # Form data
to_model(180, "models/request.py", "CreateOrder")                          # JSON POST body

# Advanced transformations
to_model(123, "models/clean.py", "Clean", expr="{k: v for k, v in json.loads(body).items() if k != 'meta'}")
to_model(123, "models/merged.py", "Merged", expr="{**json.loads(body), 'url': event['params']['response']['url']}")
```

#### Tips
- **Check structure:** `body({id})` - preview body before generating
- **Find requests:** `events({"method": "Network.requestWillBeSent", "url": "*api/orders*"})` - locate POST events
- **Form data:** `expr="dict(urllib.parse.parse_qsl(body))"` for application/x-www-form-urlencoded
- **Nested extraction:** `json_path="data[0]"` for JSON with wrapper objects
- **Custom transforms:** `expr` has `body` (str) and `event` (dict) variables available
- **Organization:** Paths like `"models/customers/group.py"` create directory structure automatically
- **Field mapping:** Add `Field(alias="...")` after generation for API field names

### quicktype
Generate types from request or response bodies. Supports TypeScript, Go, Rust, Python, and 10+ other languages.

#### Examples
```python
# Response bodies
quicktype(123, "types/User.ts", "User")                                    # TypeScript
quicktype(123, "api.go", "ApiResponse")                                    # Go struct
quicktype(123, "schema.json", "Schema")                                    # JSON Schema
quicktype(123, "types.ts", "User", json_path="data[0]")                    # Extract nested

# Request bodies (POST/PUT/PATCH)
quicktype(172, "types/JobCard.ts", "JobCardForm", expr="dict(urllib.parse.parse_qsl(body))")  # Form data
quicktype(180, "types/CreateOrder.ts", "CreateOrderRequest")               # JSON POST body

# Advanced options
quicktype(123, "types.ts", "User", options={"readonly": True})             # TypeScript readonly
quicktype(123, "types.ts", "Clean", expr="{k: v for k, v in json.loads(body).items() if k != 'meta'}")
```

#### Tips
- **Check structure:** `body({id})` - preview body before generating
- **Find requests:** `events({"method": "Network.requestWillBeSent", "url": "*api*"})` - locate POST events
- **Form data:** `expr="dict(urllib.parse.parse_qsl(body))"` for application/x-www-form-urlencoded
- **Nested extraction:** `json_path="data[0]"` for JSON with wrapper objects
- **Languages:** .ts/.go/.rs/.java/.kt/.swift/.cs/.cpp/.dart/.rb/.json extensions set language
- **Options:** Dict keys map to CLI flags: `{"readonly": True}` → `--readonly`, `{"nice_property_names": True}` → `--nice-property-names`. See `quicktype --help` for language-specific flags
- **Common options:** TypeScript: `{"readonly": True, "prefer_types": True}`, Go: `{"omit_empty": True}`, Python: `{"pydantic_base_model": True}`
- **Install:** `npm install -g quicktype` if command not found
- **Pydantic models:** Use `to_model({id}, "models/model.py", "Model")` for Pydantic v2 instead

### inspect
Inspect CDP events with full Python debugging.

Available objects: 'data' (when inspecting event), 'cdp' and 'state' (when no event).

#### Examples
```python
inspect(456)                               # Full event
inspect(456, "data['method']")             # Event type
inspect(456, "list(data.keys())")          # Top-level keys
inspect(456, "data.get('params', {}).get('response', {}).get('status')")
inspect(456, "re.findall(r'session=(\\w+)', str(data))")  # Extract patterns
inspect(456, "base64.b64decode(data['params']['response']['body'])")
inspect(456, "jwt.decode(auth.replace('Bearer ', ''), options={'verify_signature': False})")
inspect(expr="len(cdp.events)")           # Direct CDP access
inspect(expr="[e for e in cdp.events if 'error' in str(e).lower()][:3]")
```

#### Tips
- **Find related:** `events({'requestId': data.get('params', {}).get('requestId')})`
- **Compare events:** `inspect(other_id, "data.get('method')")`
- **Extract timing:** `inspect({id}, "data['params']['timing']")`
- **Decode cookies:** `inspect({id}, "[c.split('=') for c in data.get('params', {}).get('cookies', '').split(';')]")`
- **Get body:** `body({id})` - if this is a response event

### network
Show network requests with full data.

#### Tips
- **Analyze responses:** `body({id})` - fetch response body
- **Generate models:** `to_model({id}, "models/model.py", "Model")` - create Pydantic models from JSON
- **Parse HTML:** `body({id}, "bs4(body, 'html.parser').find('title').text")`
- **Extract JSON:** `body({id}, "json.loads(body)['data']")`
- **Find patterns:** `body({id}, "re.findall(r'/api/\\w+', body)")`
- **Decode JWT:** `body({id}, "jwt.decode(body, options={'verify_signature': False})")`
- **Search events:** `events({'url': '*api*'})` - find all API calls
- **Intercept traffic:** `fetch('enable')` then `requests()` - pause and modify

### console
Show console messages with full data.

#### Tips
- **Inspect error:** `inspect({id})` - view full stack trace
- **Find all errors:** `events({'level': 'error'})` - filter console errors
- **Extract stack:** `inspect({id}, "data.get('stackTrace', {})")`
- **Search messages:** `events({'message': '*failed*'})` - pattern match
- **Check network:** `network()` - may show failed requests causing errors

### events
Query CDP events by field values with automatic discovery.

Searches across ALL event types - network, console, page, etc.
Field names are discovered automatically and case-insensitive.

#### Examples
```python
events()                                    # Recent 20 events
events({"method": "Runtime.*"})            # Runtime events
events({"requestId": "123"}, limit=100)    # Specific request
events({"url": "*api*"})                   # Find all API calls
events({"status": 200})                    # Successful responses
events({"level": "error"})                # Console errors
```

#### Tips
- **Inspect full event:** `inspect({id})` - view complete CDP data
- **Extract nested data:** `inspect({id}, "data['params']['response']['headers']")`
- **Find patterns:** `inspect({id}, "re.findall(r'token=(\\w+)', str(data))")`
- **Get response body:** `body({id})` - if this is a network response
- **Decode data:** `inspect({id}, "base64.b64decode(data.get('params', {}).get('body', ''))")`

### js
Execute JavaScript in the browser. Uses fresh scope by default to avoid redeclaration errors.

#### Scope Behavior
**Default (fresh scope)** - Each call runs in isolation:
```python
js("const x = 1")    # ✓ x isolated
js("const x = 2")    # ✓ No error, fresh scope
```

**Persistent scope** - Variables survive across calls:
```python
js("var data = {count: 0}", persist=True)    # data persists
js("data.count++", persist=True)              # Modifies data
js("data.count", persist=True)                # Returns 1
```

**With browser element** - Always fresh scope:
```python
js("element.offsetWidth", selection=1)       # Use element #1
js("element.classList", selection=2)         # Use element #2
```

#### Examples
```python
# Basic queries
js("document.title")                           # Get page title
js("[...document.links].map(a => a.href)")    # Get all links
js("document.body.innerText.length")           # Text length

# Async operations
js("fetch('/api').then(r => r.json())", await_promise=True)

# DOM manipulation (no return)
js("document.querySelectorAll('.ad').forEach(e => e.remove())", wait_return=False)

# Persistent state for multi-step operations
js("var apiData = null", persist=True)
js("fetch('/api').then(r => r.json()).then(d => apiData = d)", persist=True, await_promise=True)
js("apiData.users.length", persist=True)
```

#### Tips
- **Fresh scope:** Default behavior prevents const/let redeclaration errors
- **Persistent state:** Use `persist=True` for multi-step operations or global hooks
- **No return needed:** Set `wait_return=False` for DOM manipulation or hooks
- **Browser selections:** Use `selection=N` with browser() to operate on selected elements
- **Check console:** `console()` - see logged messages from JS execution
- **Hook fetch:** `js("window.fetch = new Proxy(fetch, {apply: (t, _, a) => {console.log(a); return t(...a)}})", persist=True, wait_return=False)`

### fetch
Control request interception for debugging and modification.

#### Examples
```python
fetch("status")                           # Check status
fetch("enable")                           # Enable request stage
fetch("enable", {"response": true})       # Both stages
fetch("disable")                          # Disable
```

#### Tips
- **View paused:** `requests()` - see all intercepted requests
- **Inspect request:** `inspect({id})` - view full CDP event data
- **Analyze body:** `body({id})` - fetch and examine response body
- **Resume request:** `resume({id})` - continue the request
- **Modify request:** `resume({id}, modifications={'url': '...'})`
- **Block request:** `fail({id}, 'BlockedByClient')` - reject the request

### requests
Show paused requests and responses.

#### Tips
- **Inspect request:** `inspect({id})` - view full CDP event data
- **Analyze body:** `body({id})` - fetch and examine response body
- **Resume request:** `resume({id})` - continue the request
- **Modify request:** `resume({id}, modifications={'url': '...'})`
- **Fail request:** `fail({id}, 'BlockedByClient')` - block the request

### page
Get current page information and navigate.

#### Tips
- **Navigate:** `navigate("https://example.com")` - go to URL
- **Reload:** `reload()` or `reload(ignore_cache=True)` - refresh page
- **History:** `back()`, `forward()`, `history()` - navigate history
- **Execute JS:** `js("document.title")` - run JavaScript in page
- **Monitor traffic:** `network()` - see requests, `console()` - see messages
- **Switch page:** `pages()` then `connect(page=N)` - change to another tab
- **Full status:** `status()` - connection details and event count

### pages
List available Chrome pages and manage connections.

#### Tips
- **Connect to page:** `connect(page={index})` - connect by index number
- **Connect by ID:** `connect(page_id="{page_id}")` - stable across tab reordering
- **Switch pages:** Just call `connect()` again - no need to disconnect first
- **Check status:** `status()` - see current connection and event count
- **Reconnect:** If connection lost, select page and `connect()` again
- **Find page:** Look for title/URL in table - index stays consistent

### selections
Browser element selections with prompt and analysis.

Access selected DOM elements and their properties via Python expressions. Elements are selected using the Chrome extension's selection mode.

#### Examples
```python
selections()                                    # View all selections
selections(expr="data['prompt']")              # Get prompt text
selections(expr="data['selections']['1']")     # Get element #1 data
selections(expr="data['selections']['1']['styles']")  # Get styles
selections(expr="len(data['selections'])")     # Count selections
selections(expr="{k: v['selector'] for k, v in data['selections'].items()}")  # All selectors
```

#### Tips
- **Extract HTML:** `selections(expr="data['selections']['1']['outerHTML']")` - get element HTML
- **Get CSS selector:** `selections(expr="data['selections']['1']['selector']")` - unique selector
- **Use with js():** `js("element.offsetWidth", selection=1)` - integrate with JavaScript execution
- **Access styles:** `selections(expr="data['selections']['1']['styles']['display']")` - computed CSS
- **Get attributes:** `selections(expr="data['selections']['1']['preview']")` - tag, id, classes
- **Inspect in prompts:** Use `@webtap:webtap://selections` resource in Claude Code for AI analysis