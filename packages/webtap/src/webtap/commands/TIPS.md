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

### request
Get HAR request details with field selection and Python expressions.

#### Examples
```python
request(123)                           # Minimal (method, url, status)
request(123, ["*"])                    # Everything
request(123, ["request.headers.*"])    # Request headers
request(123, ["response.content"])     # Fetch response body
request(123, ["request.postData", "response.content"])  # Both bodies
request(123, ["response.content"], expr="json.loads(data['response']['content']['text'])")  # Parse JSON
```

#### Tips
- **Field patterns:** `["request.*"]`, `["response.headers.*"]`, `["response.content"]`
- **Expression:** `expr` has access to selected data as `data` variable
- **Parse JSON:** `expr="json.loads(data['response']['content']['text'])"`
- **Generate models:** `to_model(id, "models/model.py", "Model")` - create Pydantic from body
- **Generate types:** `quicktype(id, "types.ts", "Type")` - TypeScript/other languages

### to_model
Generate Pydantic v2 models from request or response bodies.

Uses HAR row ID from `network()` output with explicit field selection.

#### Examples
```python
# Response bodies (default)
to_model(5, "models/product.py", "Product")
to_model(5, "models/user.py", "User", json_path="data[0]")

# Request bodies (POST/PUT/PATCH)
to_model(5, "models/form.py", "Form", field="request.postData")
to_model(5, "models/form.py", "Form", field="request.postData", expr="dict(urllib.parse.parse_qsl(body))")

# Advanced transformations
to_model(5, "models/clean.py", "Clean", expr="{k: v for k, v in json.loads(body).items() if k != 'meta'}")
```

#### Tips
- **Preview body:** `request(id, ["response.content"])` - check structure before generating
- **Find requests:** `network(url="*api*")` - locate API calls
- **Form data:** `field="request.postData"` with `expr="dict(urllib.parse.parse_qsl(body))"`
- **Nested extraction:** `json_path="data[0]"` for JSON with wrapper objects
- **Custom transforms:** `expr` has `body` (str) variable available
- **Organization:** Paths like `"models/customers/group.py"` create directory structure automatically

### quicktype
Generate types from request or response bodies. Supports TypeScript, Go, Rust, Python, and 10+ other languages.

Uses HAR row ID from `network()` output with explicit field selection.

#### Examples
```python
# Response bodies (default)
quicktype(5, "types/User.ts", "User")
quicktype(5, "api.go", "ApiResponse")
quicktype(5, "schema.json", "Schema")
quicktype(5, "types.ts", "User", json_path="data[0]")

# Request bodies (POST/PUT/PATCH)
quicktype(5, "types/Form.ts", "Form", field="request.postData")
quicktype(5, "types/Form.ts", "Form", field="request.postData", expr="dict(urllib.parse.parse_qsl(body))")

# Advanced options
quicktype(5, "types.ts", "User", options={"readonly": True})
```

#### Tips
- **Preview body:** `request(id, ["response.content"])` - check structure before generating
- **Find requests:** `network(url="*api*")` - locate API calls
- **Form data:** `field="request.postData"` with `expr="dict(urllib.parse.parse_qsl(body))"`
- **Nested extraction:** `json_path="data[0]"` for JSON with wrapper objects
- **Languages:** .ts/.go/.rs/.java/.kt/.swift/.cs/.cpp/.dart/.rb/.json extensions set language
- **Options:** Dict keys map to CLI flags: `{"readonly": True}` → `--readonly`
- **Install:** `npm install -g quicktype` if command not found
- **Pydantic:** Use `to_model(id, "models/model.py", "Model")` for Pydantic v2 instead

### network
Show network requests with full data. Use `req_state="paused"` to filter paused requests.

#### Tips
- **Analyze responses:** `request({id}, ["response.content"])` - fetch response body
- **Generate models:** `to_model({id}, "models/model.py", "Model")` - create Pydantic models from JSON
- **Parse HTML:** `request({id}, ["response.content"], expr="bs4(data['response']['content']['text'], 'html.parser').find('title').text")`
- **Extract JSON:** `request({id}, ["response.content"], expr="json.loads(data['response']['content']['text'])['data']")`
- **Find patterns:** `network(url="*api*")` - filter by URL pattern
- **View paused only:** `network(req_state="paused")` - show only paused requests
- **Intercept traffic:** `fetch('enable')` then `resume({id})` or `fail({id})` to control

### console
Show console messages with full data.

#### Tips
- **Filter errors:** `console(level="error")` - show only errors
- **Check network:** `network()` - may show failed requests causing errors
- **Debug with js:** `js("console.log('debug:', myVar)")` - add console output

### js
Execute JavaScript in the browser. Uses fresh scope by default to avoid redeclaration errors.

#### Expression Mode (Important!)
Default mode wraps code as `return (code)`, so **use single expressions only**:
```python
js("document.title")                    # ✓ Single expression
js("1 + 2 + 3")                         # ✓ Single expression
js("[...document.links].map(a=>a.href)") # ✓ Single expression (chained)
js("const x = 1; x + 1")               # ✗ Multi-statement fails (semicolon)
js("let y = 2; return y")              # ✗ Fails - already wrapped in return
```

For multi-statement code, use `persist=True` (runs in global scope, not wrapped):
```python
js("var x = 1; x + 1", persist=True)   # ✓ Multi-statement works
js("const arr = [1,2,3]; arr.map(x => x*2)", persist=True)  # ✓ Works
```

#### Scope Behavior
**Default (fresh scope)** - Each call runs in isolation via IIFE wrapper:
```python
js("document.title")     # ✓ Returns title
js("document.title")     # ✓ No redeclaration issues
```

**Persistent scope** - Variables survive across calls (global scope):
```python
js("var data = {count: 0}", persist=True)    # data persists
js("data.count++", persist=True)              # Modifies data
js("data.count", persist=True)                # Returns 1
```

**With browser element** - Always fresh scope (element injected):
```python
js("element.offsetWidth", selection=1)       # Use element #1
js("element.classList", selection=2)         # Use element #2
```

#### Examples
```python
# Basic queries (single expressions)
js("document.title")                           # Get page title
js("[...document.links].map(a => a.href)")    # Get all links
js("document.body.innerText.length")           # Text length

# Async operations
js("fetch('/api').then(r => r.json())", await_promise=True)

# DOM manipulation (no return)
js("document.querySelectorAll('.ad').forEach(e => e.remove())", wait_return=False)

# Multi-statement operations (use persist=True)
js("var apiData = null", persist=True)
js("fetch('/api').then(r => r.json()).then(d => apiData = d)", persist=True, await_promise=True)
js("apiData.users.length", persist=True)
```

#### Tips
- **Expression mode:** Default wraps as `return (code)` - use single expressions or `persist=True`
- **Fresh scope:** Default behavior prevents const/let redeclaration errors
- **Persistent state:** Use `persist=True` for multi-step operations, global hooks, or multi-statement code
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
- **View paused:** `network(req_state="paused")` or `requests()` - see intercepted requests
- **View details:** `request({id})` - view request/response data
- **Resume request:** `resume({id})` - continue the request
- **Modify request:** `resume({id}, modifications={'url': '...'})`
- **Block request:** `fail({id}, 'BlockedByClient')` - reject the request
- **Mock response:** `fulfill({id}, body='{"ok":true}')` - return custom response without server

### requests
Show paused requests. Equivalent to `network(req_state="paused")`.

#### Tips
- **View details:** `request({id})` - view request/response data
- **Resume request:** `resume({id})` - continue the request
- **Modify request:** `resume({id}, modifications={'url': '...'})`
- **Fail request:** `fail({id}, 'BlockedByClient')` - block the request
- **Mock response:** `fulfill({id}, body='...')` - return custom response

### fulfill
Fulfill a paused request with a custom response without hitting the server.

#### Examples
```python
fulfill(583)                                    # Empty 200 response
fulfill(583, body='{"ok": true}')              # JSON response
fulfill(583, body="Not Found", status=404)     # Error response
fulfill(583, headers=[{"name": "Content-Type", "value": "application/json"}])
```

#### Tips
- **Mock APIs:** Return fake JSON during development without backend
- **Test errors:** `fulfill({id}, body="Error", status=500)` - test error handling
- **Set headers:** Use `headers=[{"name": "...", "value": "..."}]` for content-type etc.
- **View paused:** `network(req_state="paused")` - find requests to fulfill

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
