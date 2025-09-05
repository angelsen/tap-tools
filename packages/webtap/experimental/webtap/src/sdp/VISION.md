# Svelte Debug Protocol (SDP) Vision

## Overview

The Svelte Debug Protocol (SDP) is a framework-aware debugging protocol that complements Chrome DevTools Protocol (CDP) by providing deep insights into Svelte application state, component lifecycle, and reactivity chains.

## Core Philosophy

**Observe, Don't Interfere**: SDP should be transparent to the application, capturing state changes and component interactions without affecting performance or behavior.

## Protocol Design

### Event Structure (CDP-like)

```json
{
  "method": "Svelte.stateChanged",
  "params": {
    "componentId": "TodoList-1",
    "componentType": "TodoList",
    "statePath": "items[0].completed",
    "oldValue": false,
    "newValue": true,
    "timestamp": 1234567890,
    "triggeredBy": "click"
  }
}
```

### Domain Categories

#### 1. Component Domain
- `Component.mounted` - Component instance created
- `Component.updated` - Component re-rendered
- `Component.destroyed` - Component removed from DOM
- `Component.propsChanged` - Props updated from parent

#### 2. State Domain
- `State.initialized` - $state rune initialized
- `State.changed` - $state value changed
- `State.derived` - $derived value recomputed
- `State.snapshot` - Full state snapshot captured

#### 3. Effect Domain
- `Effect.triggered` - $effect ran
- `Effect.scheduled` - $effect queued
- `Effect.completed` - $effect finished
- `Effect.error` - $effect threw error

#### 4. Store Domain
- `Store.subscribed` - Store subscription created
- `Store.updated` - Store value changed
- `Store.unsubscribed` - Store subscription removed

#### 5. Reactivity Domain
- `Reactivity.chainStarted` - Reactivity update began
- `Reactivity.invalidated` - Dependencies marked dirty
- `Reactivity.computed` - Values recomputed
- `Reactivity.chainCompleted` - Update cycle finished

## Integration Architecture

```
Svelte App (Browser)
    ├── Svelte Runtime (with $inspect hooks)
    ├── SDP Injector (captures state/events)
    └── WebSocket/PostMessage Bridge
         ↓
    SDP Collector (WebTap)
    ├── Event Storage (DuckDB)
    ├── State Cache (for queries)
    └── Query Interface
         ↓
    Unified WebTap Interface
    ├── CDP Events (Network, DOM, etc.)
    └── SDP Events (State, Components, etc.)
```

## Key Features

### 1. State Time Travel
- Store state snapshots with timestamps
- Replay state changes synchronized with network events
- Correlate UI changes with API calls

### 2. Component Inspector
```python
# WebTap REPL
>>> svelte_tree()  # Show component hierarchy
>>> svelte_state("TodoList-1")  # Inspect component state
>>> svelte_props("Button-3")  # View component props
```

### 3. Reactivity Tracing
- Visualize dependency graphs
- Track effect cascades
- Identify performance bottlenecks

### 4. Event Correlation
```sql
-- SQL query combining CDP and SDP
SELECT 
    s.componentId,
    s.newValue as state_change,
    n.url as triggered_api_call
FROM sdp_events s
JOIN cdp_events n ON 
    n.timestamp > s.timestamp AND 
    n.timestamp < s.timestamp + 100
WHERE 
    s.method = 'State.changed' AND
    n.method = 'Network.requestWillBeSent'
```

## Implementation Strategy

### Phase 1: Read-Only Observation
- Capture state changes via $inspect
- Log component lifecycle events
- Store in DuckDB alongside CDP events

### Phase 2: State Querying
- Query component state on-demand
- Build component tree representation
- Provide state diff functionality

### Phase 3: Interactive Debugging
- Modify component state via commands
- Trigger effects manually
- Set state breakpoints

### Phase 4: Advanced Analysis
- Performance profiling
- Memory leak detection
- Reactivity optimization suggestions

## Technical Approach

### Svelte 5 Rune Integration

```javascript
// Automatic state tracking via $inspect
let count = $state(0);
$inspect(count); // SDP captures all changes

// Effect monitoring
$effect(() => {
    // SDP tracks when this runs
    console.log(count);
});
```

### Injection Methods

1. **Development Mode**: Use Vite plugin for auto-injection
2. **Production Mode**: Browser extension content script
3. **Testing Mode**: Direct import in test files

## Benefits Over Traditional Debugging

1. **Framework Awareness**: Understand Svelte-specific concepts
2. **Unified Timeline**: Correlate frontend and backend events
3. **SQL Queryability**: Complex analysis via DuckDB
4. **Zero Configuration**: Works automatically with any Svelte 5 app
5. **Performance Insights**: Identify unnecessary re-renders

## Success Metrics

- Capture 100% of state changes without performance impact
- Query any component state within 10ms
- Correlate UI events with network requests
- Provide actionable performance recommendations

## Future Possibilities

1. **Cross-Framework Protocol**: Extend to React (RDP), Vue (VDP)
2. **AI-Powered Analysis**: Pattern detection in state changes
3. **Collaborative Debugging**: Share debug sessions
4. **Production Monitoring**: Lightweight SDP for production apps

## Comparison with Existing Tools

| Feature | Chrome DevTools | Svelte DevTools | SDP |
|---------|----------------|-----------------|-----|
| Network Inspection | ✓ | ✗ | ✓ (via CDP) |
| Component Tree | ✗ | ✓ | ✓ |
| State Time Travel | ✗ | ✗ | ✓ |
| SQL Queries | ✗ | ✗ | ✓ |
| Event Correlation | ✗ | ✗ | ✓ |
| Performance Tracing | ✓ | ✗ | ✓ |

## Guiding Principles

1. **Non-Invasive**: Never require code changes in the app
2. **Performance-First**: < 1% overhead in production
3. **Developer-Friendly**: Intuitive API matching CDP patterns
4. **Extensible**: Plugin architecture for custom domains
5. **Framework-Agnostic Core**: SDP pattern applicable to any framework