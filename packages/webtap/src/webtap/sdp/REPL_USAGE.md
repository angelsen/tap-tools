# SDP REPL Usage Guide

## Quick Start

### 1. Start the Svelte app (in terminal 1):
```bash
cd packages/webtap/svelte_dev/svelte-debug-lab
deno task dev
# Opens at http://localhost:5173
```

### 2. Start Python REPL with SDP (in terminal 2):
```python
# Start Python in the tap-tools directory
cd packages/webtap
python3

# In the Python REPL:
>>> from src.webtap.sdp import start_sync, SDPCollector
>>> 
>>> # Start the SDP collector (synchronous for REPL)
>>> sdp = start_sync(port=8766, verbose=True)
>>> 
>>> # Now open http://localhost:5173 in browser
>>> # The Svelte app will auto-connect via WebSocket
>>> 
>>> # Interact with the Svelte app, then check events:
>>> sdp.events  # List all captured events
>>> sdp.state   # Current state cache
>>> sdp.get_state('count')  # Get specific state value
```

## Async Version (for notebooks or async REPL):
```python
import asyncio
from src.webtap.sdp import SDPCollector

# Create and start collector
sdp = SDPCollector(port=8766, verbose=True)
await sdp.start()

# Events will be printed as they arrive
# Query data:
sdp.events
sdp.get_state('count')
sdp.get_component_tree()
sdp.filter_events(method='stateChanged')
```

## Manual WebSocket Testing

### From Browser Console:
```javascript
// Connect to SDP collector
ws = new WebSocket('ws://localhost:8766/sdp');

// Send test event
ws.onopen = () => {
  ws.send(JSON.stringify({
    method: 'Svelte.stateChanged',
    params: {
      componentId: 'test-123',
      componentType: 'TestComponent',
      statePath: 'count',
      oldValue: 0,
      newValue: 1,
      timestamp: Date.now()
    }
  }));
};
```

### From Python (manual WebSocket):
```python
import asyncio
import websockets
import json

async def test_sdp():
    async with websockets.connect('ws://localhost:8766/sdp') as ws:
        event = {
            'method': 'Svelte.stateChanged',
            'params': {
                'componentId': 'py-test',
                'statePath': 'testValue',
                'newValue': 42
            }
        }
        await ws.send(json.dumps(event))
        print("Event sent!")

asyncio.run(test_sdp())
```

## Available Methods

### SDPCollector Methods:
- `sdp.events` - All collected events
- `sdp.state` - Current state cache
- `sdp.components` - Component registry
- `sdp.get_state(path)` - Get state by path
- `sdp.get_component_tree()` - Component hierarchy
- `sdp.get_recent_events(n)` - Last n events
- `sdp.filter_events(method, component_type)` - Filter events
- `sdp.clear()` - Clear all data

### For sync REPL (SDPHandle):
- `sdp.process_events()` - Process pending WebSocket messages
- `sdp.events` - Auto-processes then returns events
- `sdp.state` - Auto-processes then returns state

## Event Types

The Svelte app sends these event types:

1. **Svelte.stateChanged** - When $state values change
2. **Svelte.derivedChanged** - When $derived values update
3. **Svelte.effectTriggered** - When $effect runs
4. **Svelte.componentMounted** - Component lifecycle
5. **Svelte.componentDestroyed** - Component cleanup
6. **Svelte.userInteraction** - User actions (clicks, input)

## Example Session

```python
>>> from src.webtap.sdp import start_sync
>>> sdp = start_sync()
[SDP] Starting WebSocket server on ws://localhost:8766/sdp
[SDP] Server ready. Connect from Svelte app.

# Open browser to http://localhost:5173
# Click "Increment" button a few times

[SDP Event] Svelte.componentMounted
  Component: TestPage mounted
  Initial state: {'count': 0, 'message': 'Hello SDP', ...}

[SDP Event] Svelte.userInteraction
  Type: click
  Target: increment-button
  Result: {'count': 1}

[SDP Event] Svelte.stateChanged
  Component: TestPage (a3f2c8d9...)
  Path: count
  Value: 0 → 1

>>> sdp.get_state('count')
1

>>> sdp.get_state('doubled')
2

>>> len(sdp.events)
15

>>> sdp.filter_events(method='stateChanged')
[{'method': 'Svelte.stateChanged', 'params': {...}}, ...]
```

## Combining with CDP

In WebTap REPL, you could correlate SDP and CDP events:

```python
# Theoretical future integration
>>> from webtap import connect, events
>>> from webtap.sdp import start_sync

>>> # Connect to Chrome
>>> connect(0)

>>> # Start SDP collector
>>> sdp = start_sync()

>>> # Interact with app...

>>> # Query CDP network events
>>> network_events = events(method="Network.*")

>>> # Query SDP state changes
>>> state_changes = sdp.filter_events(method='stateChanged')

>>> # Correlate by timestamp
>>> for state in state_changes:
...     ts = state['params']['timestamp']
...     # Find network calls within 100ms
...     related = [n for n in network_events 
...                if abs(n['timestamp'] - ts) < 100]
...     if related:
...         print(f"State change triggered {len(related)} API calls")
```

## Troubleshooting

1. **WebSocket won't connect**: 
   - Check port 8766 is free
   - Ensure CORS is allowed (Svelte dev server)
   - Check browser console for errors

2. **No events arriving**:
   - Verify Svelte app has `$inspect` calls
   - Check browser console for [SDP] logs
   - Ensure WebSocket connected (check Network tab)

3. **Events lost in sync mode**:
   - Call `sdp.process_events()` periodically
   - Or use async mode for real-time processing