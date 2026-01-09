# WebTap Command Documentation

## Libraries
All commands have these pre-imported (no imports needed!):
- **Web:** bs4/BeautifulSoup, lxml, ElementTree/ET
- **Data:** json, yaml, msgpack, protobuf_json/protobuf_text
- **Security:** jwt, base64, hashlib, cryptography
- **HTTP:** httpx, urllib
- **Text:** re, difflib, textwrap, html
- **Utils:** datetime, collections, itertools, pprint, ast

## Parameter Reference

### Target vs Row ID
- **Target ID**: Chrome page identifier (e.g., `"9222:abc123"`) - from `pages()` output
- **Row ID**: Integer from `network()` or `console()` output - used with `request()`, `entry()`

### Commands with `target` parameter
| Command | Signature | Target Position |
|---------|-----------|-----------------|
| `js` | `js(code, target, ...)` | REQUIRED, 2nd |
| `navigate` | `navigate(url, target)` | REQUIRED, 2nd |
| `reload` | `reload(target, ...)` | REQUIRED, 1st |
| `back` | `back(target)` | REQUIRED, 1st |
| `forward` | `forward(target)` | REQUIRED, 1st |
| `network` | `network(target=None, ...)` | OPTIONAL, 1st |
| `console` | `console(target=None, ...)` | OPTIONAL, 1st |

### Commands WITHOUT `target`
| Command | Key Parameters |
|---------|----------------|
| `request` | `request(id, fields, expr, output)` |
| `entry` | `entry(id, fields, expr, output)` |
| `to_model` | `to_model(id, output, model_name, ...)` |
| `quicktype` | `quicktype(id, output, type_name, ...)` |
| `fetch` | `fetch(rules)` |
| `selections` | `selections(expr)` |
| `filters` | `filters(add, remove, enable, disable, hide)` |
| `targets` | `targets()` - show connected targets |

### REPL-Only Commands (not exposed via MCP)
| Command | Purpose |
|---------|---------|
| `connect` | `connect(target="")` - connect to Chrome page |
| `disconnect` | `disconnect(target="")` - disconnect from Chrome |
| `pages` | `pages()` - list available pages |
| `status` | `status()` - full connection status |
| `page` | `page()` - current page info |
| `ports` | `ports()` - manage debug ports |

### Connected Target Context
`network()` and `console()` responses include a `targets` field with all connected targets:
```python
{
    "targets": [
        {"target": "9222:abc123", "title": "My Page", "url": "https://..."}
    ],
    "requests": [...]  # or "messages": [...]
}
```
Use `targets()` resource when there's no traffic yet to check what's connected.

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
- **Preview body:** `request(5, ["response.content"])` - check structure before generating (5 = row ID)
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
- **Preview body:** `request(5, ["response.content"])` - check structure before generating (5 = row ID)
- **Find requests:** `network(url="*api*")` - locate API calls
- **Form data:** `field="request.postData"` with `expr="dict(urllib.parse.parse_qsl(body))"`
- **Nested extraction:** `json_path="data[0]"` for JSON with wrapper objects
- **Languages:** .ts/.go/.rs/.java/.kt/.swift/.cs/.cpp/.dart/.rb/.json extensions set language
- **Options:** Dict keys map to CLI flags: `{"readonly": True}` → `--readonly`
- **Install:** `npm install -g quicktype` if command not found
- **Pydantic:** Use `to_model(5, "models/model.py", "Model")` for Pydantic v2 instead

### network
Show network requests with full data. Use row ID from output with `request()`.

#### Tips
- **Analyze responses:** `request({id}, ["response.content"])` - fetch response body
- **Generate models:** `to_model({id}, "models/model.py", "Model")` - create Pydantic models from JSON
- **Parse HTML:** `request({id}, ["response.content"], expr="BeautifulSoup(data['response']['content']['text'], 'html.parser').find('title').text")`
- **Extract JSON:** `request({id}, ["response.content"], expr="json.loads(data['response']['content']['text'])['data']")`
- **Find patterns:** `network(url="*api*")` - filter by URL pattern
- **Auto-capture:** Response bodies captured by default on connect

### console
Show console messages. Use `target` to filter by specific Chrome tab.

#### Tips
- **View messages:** `console()` or `console("9222:abc123")` - show console output
- **Check network:** `network()` - may show failed requests causing errors
- **Debug with js:** `js("console.log('debug:', myVar)", "9222:abc123")` - add console output
- **Drill down:** `entry({id})` - view full console entry details with stack trace

### entry
Get console entry details with field selection and Python expressions.

Uses row ID from `console()` output with flexible field patterns.

#### Examples
```python
entry(5)                    # Minimal (level, message, source)
entry(5, ["*"])             # Full CDP event
entry(5, ["stackTrace"])    # Stack trace only
entry(5, ["args.*"])        # All arguments
entry(5, expr="len(data['args'])")  # Count arguments
entry(5, ["*"], output="error.json")  # Export to file
```

#### Tips
- **Field patterns:** `["stackTrace"]`, `["args.*"]`, `["args.0"]`
- **Expression:** `expr` has access to selected data as `data` variable
- **Stack traces:** Automatically formatted as `at funcName (file:line:col)`
- **Debug errors:** `console()` then `entry(5)` for full details (5 = row ID from console output)
- **Extract args:** `expr="data['args'][0]['value']"` - get first argument value

### js
Execute JavaScript in the browser. Uses fresh scope by default (REPL mode).

#### Code Style
Both expressions and declarations work in default mode:
```python
js("document.title", "9222:abc123")                           # ✓ Expression
js("const x = 1; x + 1", "9222:abc123")                       # ✓ Multi-statement
js("[...document.links].map(a => a.href)", "9222:abc123")    # ✓ Chained expression
js("let arr = [1,2,3]; arr.map(x => x*2)", "9222:abc123")    # ✓ Declaration + expression
```

#### Scope Behavior
**Default (fresh scope)** - Each call runs in REPL mode, isolated scope:
```python
js("const x = 1; x", "9222:abc123")     # ✓ Returns 1
js("const x = 2; x", "9222:abc123")     # ✓ Returns 2 (no redeclaration error)
```

**Persistent scope** - Variables survive across calls (global scope):
```python
js("var data = {count: 0}", "9222:abc123", persist=True)    # data persists
js("data.count++", "9222:abc123", persist=True)              # Modifies data
js("data.count", "9222:abc123", persist=True)                # Returns 1
```

**With browser element** - Fresh scope with `element` variable bound:
```python
js("element.offsetWidth", "9222:abc123", selection=1)       # Use element #1
js("element.classList", "9222:abc123", selection=2)         # Use element #2
```

Note: `selection` and `persist=True` cannot be combined (use manual element binding).

#### Examples
```python
# Basic queries
js("document.title", "9222:abc123")                           # Get page title
js("[...document.links].map(a => a.href)", "9222:abc123")    # Get all links
js("document.body.innerText.length", "9222:abc123")           # Text length

# Multi-statement
js("const links = [...document.links]; links.filter(a => a.href.includes('api')).length", "9222:abc123")

# Async operations
js("fetch('/api').then(r => r.json())", "9222:abc123", await_promise=True)

# DOM manipulation (no return)
js("document.querySelectorAll('.ad').forEach(e => e.remove())", "9222:abc123", wait_return=False)

# Persistent state across calls
js("var apiData = null", "9222:abc123", persist=True)
js("fetch('/api').then(r => r.json()).then(d => apiData = d)", "9222:abc123", persist=True, await_promise=True)
js("apiData.users.length", "9222:abc123", persist=True)
```

#### Tips
- **Fresh scope:** Default prevents const/let redeclaration errors across calls
- **Persistent state:** Use `persist=True` for multi-step operations or global hooks
- **No return needed:** Set `wait_return=False` for DOM manipulation or hooks
- **Browser selections:** Use `selection=N` with selections() to operate on selected elements
- **Check console:** `console("9222:abc123")` - see logged messages from JS execution
- **Hook fetch:** `js("window.fetch = new Proxy(fetch, {apply: (t, _, a) => {console.log(a); return t(...a)}})", "9222:abc123", persist=True, wait_return=False)`

### fetch
Control fetch interception. Capture is enabled by default on connect. Block/mock rules are per-target.

#### Examples
```python
fetch()                                     # Show capture state + per-target rules
fetch({"capture": False})                   # Disable capture globally
fetch({"capture": True})                    # Re-enable capture globally
fetch({"mock": {"*api*": '{"ok":1}'}, "target": "9222:abc123"})   # Mock for target
fetch({"block": ["*tracking*", "*ads*"], "target": "9222:abc123"}) # Block for target
fetch({"target": "9222:abc123"})            # Clear rules for target
```

#### Tips
- **Auto-capture:** Response bodies captured by default on connect
- **View bodies:** `request(5, ["response.content"])` - inspect captured responses (5 = row ID)
- **Block requests:** `fetch({"block": ["*pattern*"], "target": "9222:abc123"})` - fail matching URLs
- **Mock APIs:** `fetch({"mock": {"*api*": '{"test":1}'}, "target": "9222:abc123"})` - return fake responses
- **Custom status:** `fetch({"mock": {"*api*": {"body": "...", "status": 404}}, "target": "9222:abc123"})`
- **Per-target:** Block/mock rules require `"target"` parameter
- **Priority:** mock > block > capture (first match wins)
- **Clean slate:** Rules cleared on disconnect or crash

### page
Get current page information and navigate.

#### Tips
- **Navigate:** `navigate("https://example.com", "9222:abc123")` - go to URL
- **Reload:** `reload("9222:abc123")` or `reload("9222:abc123", ignore_cache=True)` - refresh page
- **History:** `back("9222:abc123")`, `forward("9222:abc123")` - navigate history
- **Execute JS:** `js("document.title", "9222:abc123")` - run JavaScript in page
- **Monitor traffic:** `network()` - see requests, `console()` - see messages

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
- **Use with js():** `js("element.offsetWidth", "9222:abc123", selection=1)` - integrate with JavaScript execution
- **Access styles:** `selections(expr="data['selections']['1']['styles']['display']")` - computed CSS
- **Get attributes:** `selections(expr="data['selections']['1']['preview']")` - tag, id, classes
- **Inspect in prompts:** Use `@webtap:webtap://selections` resource in Claude Code for AI analysis

### targets
Show connected targets and their tracking status.

#### Tips
- **Filter queries:** `network(target="{target}")` - query specific target
- **Multi-target:** When tracked, queries aggregate from tracked targets only
- **Target format:** `"port:short-id"` (e.g., `"9222:abc123"`)
