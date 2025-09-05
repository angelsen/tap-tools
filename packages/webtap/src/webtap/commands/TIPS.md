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
Fetch and analyze HTTP response bodies with Python expressions.

#### Examples
```python
body(123)                                  # Get body
body(123, "json.loads(body)")              # Parse JSON
body(123, "bs4(body, 'html.parser').find('title').text")  # HTML title
body(123, "jwt.decode(body, options={'verify_signature': False})")  # Decode JWT
body(123, "re.findall(r'/api/[^\"\\s]+', body)[:10]")  # Find API endpoints
body(123, "httpx.get(json.loads(body)['next_url']).json()")  # Chain requests
body(123, "msgpack.unpackb(body)")         # Binary formats
```

#### Tips
- **Chain requests:** `body({id}, "httpx.get(json.loads(body)['next_url']).text[:100]")`
- **Parse XML:** `body({id}, "ElementTree.fromstring(body).find('.//title').text")`
- **Extract forms:** `body({id}, "[f['action'] for f in bs4(body, 'html.parser').find_all('form')]")`
- **Decode protobuf:** `body({id}, "protobuf_json.Parse(body, YourMessage())")`
- **Find related:** `events({'requestId': request_id})` - related events

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
Execute JavaScript in the browser with optional promise handling.

#### Examples
```python
js("document.title")                           # Get page title
js("document.body.innerText.length")           # Get text length
js("[...document.links].map(a => a.href)")    # Get all links
js("fetch('/api').then(r => r.json())", await_promise=True)  # Async
js("document.querySelectorAll('.ad').forEach(e => e.remove())", wait_return=False)
js("window.fetch = new Proxy(window.fetch, {get: (t, p) => console.log(p)})", wait_return=False)
```

#### Tips
- **Extract all links:** `js("[...document.links].map(a => a.href)")`
- **Get page text:** `js("document.body.innerText")`
- **Find data attributes:** `js("[...document.querySelectorAll('[data-id]')].map(e => e.dataset)")`
- **Monitor DOM:** `js("new MutationObserver(console.log).observe(document, {childList: true, subtree: true})", wait_return=False)`
- **Hook fetch:** `js("window.fetch = new Proxy(fetch, {apply: (t, _, a) => {console.log(a); return t(...a)}})", wait_return=False)`
- **Check console:** `console()` - see logged messages from JS execution

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