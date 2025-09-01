# WebTap Svelte Development Lab

This directory contains experimental Svelte applications for developing and testing the Svelte Debug Protocol (SDP).

## Purpose

A sandbox environment to:
1. Explore Svelte 5's reactivity system and debugging capabilities
2. Prototype SDP event capture mechanisms
3. Test integration patterns with WebTap
4. Develop the bridge between Svelte state and CDP-like events

## Projects

### svelte-debug-lab/
Our main test application built with SvelteKit and Deno, featuring:
- Svelte 5 with new runes ($state, $derived, $effect, $inspect)
- TypeScript for type safety
- Tailwind CSS for styling
- Minimal setup for focused experimentation

## Development Setup

```bash
cd svelte-debug-lab
deno task dev
```

## Key Experiments

### 1. State Inspection Hook
Testing how to capture state changes using Svelte 5's `$inspect` rune:

```javascript
let count = $state(0);

// This will log all changes to count
$inspect(count);

// Goal: Redirect these logs to SDP events
```

### 2. Component Lifecycle Tracking
Monitoring component mount/unmount/update cycles:

```javascript
import { onMount, onDestroy } from 'svelte';

onMount(() => {
    // Send SDP event: Component.mounted
});
```

### 3. Effect Chain Visualization
Understanding and capturing reactivity cascades:

```javascript
let a = $state(1);
let b = $derived(a * 2);
let c = $derived(b + 1);

$effect(() => {
    // Track when this runs and why
    console.log(c);
});
```

### 4. Event Bridge Architecture
Building the connection between Svelte and WebTap:

```
Svelte Component
    ↓ ($inspect, lifecycle hooks)
SDP Collector (injected)
    ↓ (WebSocket or PostMessage)
WebTap Service
    ↓ (Store in DuckDB)
Query Interface
```

## Testing Scenarios

### Basic State Changes
- Counter increments/decrements
- Form input updates
- Toggle states

### Complex State Management
- Nested object updates
- Array mutations
- Derived state chains

### Async Operations
- API calls triggering state updates
- Loading states
- Error handling

### Component Communication
- Parent-child props flow
- Store subscriptions
- Event dispatching

## Integration Points

### With CDP
- Correlate state changes with network requests
- Link DOM mutations to component updates
- Sync console logs with state snapshots

### With WebTap
- Store SDP events in DuckDB
- Query state history with SQL
- Visualize state timeline

## Code Organization

```
svelte-debug-lab/
├── src/
│   ├── lib/
│   │   ├── sdp/           # SDP implementation
│   │   │   ├── injector.ts    # State capture logic
│   │   │   ├── events.ts      # Event formatting
│   │   │   └── bridge.ts      # WebTap connection
│   │   └── components/     # Test components
│   ├── routes/            # Test pages
│   │   ├── +layout.svelte # SDP injection point
│   │   ├── +page.svelte   # Main test UI
│   │   └── tests/         # Specific test scenarios
│   └── app.html
├── static/
├── deno.json             # Deno configuration
└── vite.config.ts        # Vite + SvelteKit config
```

## Development Workflow

1. **Implement**: Add SDP hooks to components
2. **Capture**: Collect events via $inspect and hooks
3. **Format**: Structure as CDP-like events
4. **Send**: Transmit to WebTap service
5. **Store**: Save in DuckDB
6. **Query**: Analyze with SQL

## Goals

### Short Term
- [ ] Capture basic state changes
- [ ] Track component lifecycle
- [ ] Format as SDP events
- [ ] Send to WebTap

### Medium Term
- [ ] Full reactivity chain tracking
- [ ] Store state snapshots
- [ ] Query historical state
- [ ] Correlate with CDP events

### Long Term
- [ ] Production-ready injection
- [ ] Chrome extension integration
- [ ] Performance profiling
- [ ] Cross-framework support

## Resources

- [Svelte 5 Runes](https://svelte.dev/docs/svelte/runes)
- [SvelteKit with Deno](https://kit.svelte.dev/)
- [Chrome DevTools Protocol](https://chromedevtools.github.io/devtools-protocol/)
- [WebTap Documentation](../README.md)

## Notes

This is an experimental playground. Code here is not production-ready but serves as a proving ground for SDP concepts that will eventually be integrated into WebTap proper.