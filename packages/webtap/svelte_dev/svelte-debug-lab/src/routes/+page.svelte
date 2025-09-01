<script>
  import { onMount, onDestroy } from 'svelte';
  
  // State declarations with Svelte 5 runes
  let count = $state(0);
  let message = $state('Hello SDP');
  let items = $state([
    { id: 1, text: 'Item 1', done: false },
    { id: 2, text: 'Item 2', done: false }
  ]);
  
  // Derived state
  let doubled = $derived(count * 2);
  let completedCount = $derived(items.filter(i => i.done).length);
  let stats = $derived({
    total: items.length,
    completed: completedCount,
    pending: items.length - completedCount
  });
  
  // Component metadata
  const componentId = crypto.randomUUID();
  const componentType = 'TestPage';
  
  // SDP Integration - Send events to parent window or WebSocket
  function sendSDPEvent(method, params) {
    const event = {
      method: `Svelte.${method}`,
      params: {
        ...params,
        componentId,
        componentType,
        timestamp: Date.now()
      }
    };
    
    // Send via multiple channels for testing
    // 1. Console (always available)
    console.log('[SDP]', event);
    
    // 2. Window postMessage (for extension/iframe)
    if (typeof window !== 'undefined') {
      try {
        // Ensure event is serializable by converting to JSON and back
        const serializableEvent = JSON.parse(JSON.stringify(event));
        window.postMessage({ type: 'SDP_EVENT', event: serializableEvent }, '*');
      } catch (e) {
        console.error('SDP postMessage error:', e);
      }
    }
    
    // 3. WebSocket (if available)
    if (typeof window !== 'undefined' && window.__SDP_SOCKET) {
      try {
        window.__SDP_SOCKET.send(JSON.stringify(event));
      } catch (e) {
        console.error('SDP WebSocket error:', e);
      }
    }
  }
  
  // Track state changes with $inspect
  $inspect(count).with((type, value) => {
    sendSDPEvent('stateChanged', {
      statePath: 'count',
      changeType: type,
      newValue: value,
      oldValue: type === 'init' ? undefined : count
    });
  });
  
  $inspect(message).with((type, value) => {
    sendSDPEvent('stateChanged', {
      statePath: 'message',
      changeType: type,
      newValue: value,
      oldValue: type === 'init' ? undefined : message
    });
  });
  
  $inspect(items).with((type, value) => {
    sendSDPEvent('stateChanged', {
      statePath: 'items',
      changeType: type,
      newValue: value,
      oldValue: type === 'init' ? undefined : items
    });
  });
  
  // Track derived changes
  $inspect(doubled).with((type, value) => {
    sendSDPEvent('derivedChanged', {
      derivedPath: 'doubled',
      changeType: type,
      newValue: value,
      dependencies: ['count']
    });
  });
  
  $inspect(stats).with((type, value) => {
    sendSDPEvent('derivedChanged', {
      derivedPath: 'stats',
      changeType: type,
      newValue: value,
      dependencies: ['items']
    });
  });
  
  // Track effects
  $effect(() => {
    $inspect.trace('api-effect');
    
    // Simulate API call when count changes
    if (count > 0) {
      sendSDPEvent('effectTriggered', {
        effectId: 'api-effect',
        trigger: 'count',
        value: count
      });
    }
  });
  
  // Lifecycle tracking
  onMount(() => {
    sendSDPEvent('componentMounted', {
      props: {},
      initialState: { 
        count, 
        message, 
        items: JSON.parse(JSON.stringify(items))  // Deep clone to ensure serializability
      }
    });
    
    // Setup WebSocket connection if not exists
    if (typeof window !== 'undefined' && !window.__SDP_SOCKET) {
      try {
        // Try to connect to local SDP collector
        const ws = new WebSocket('ws://localhost:8766/sdp');
        ws.onopen = () => {
          console.log('[SDP] WebSocket connected');
          window.__SDP_SOCKET = ws;
        };
        ws.onerror = (e) => {
          console.log('[SDP] WebSocket not available, using console only');
        };
      } catch (e) {
        console.log('[SDP] WebSocket setup failed:', e);
      }
    }
    
    return () => {
      sendSDPEvent('componentWillUnmount', {});
    };
  });
  
  onDestroy(() => {
    sendSDPEvent('componentDestroyed', {});
  });
  
  // User interaction handlers
  function increment() {
    count++;
    sendSDPEvent('userInteraction', {
      type: 'click',
      target: 'increment-button',
      result: { count }
    });
  }
  
  function updateMessage(event) {
    message = event.target.value;
  }
  
  function toggleItem(id) {
    const item = items.find(i => i.id === id);
    if (item) {
      item.done = !item.done;
      sendSDPEvent('userInteraction', {
        type: 'click',
        target: `toggle-item-${id}`,
        result: { itemId: id, done: item.done }
      });
    }
  }
  
  function addItem() {
    const newItem = {
      id: Math.max(...items.map(i => i.id), 0) + 1,
      text: `Item ${items.length + 1}`,
      done: false
    };
    items.push(newItem);
    sendSDPEvent('userInteraction', {
      type: 'click',
      target: 'add-item',
      result: { newItem }
    });
  }
</script>

<div class="p-8 max-w-4xl mx-auto">
  <h1 class="text-3xl font-bold mb-8">SDP Test Component</h1>
  
  <div class="grid grid-cols-2 gap-8">
    <!-- Counter Section -->
    <div class="border rounded-lg p-6">
      <h2 class="text-xl font-semibold mb-4">Counter State</h2>
      <div class="space-y-4">
        <div>
          <span class="font-mono">count:</span> {count}
        </div>
        <div>
          <span class="font-mono">doubled:</span> {doubled}
        </div>
        <button 
          onclick={increment}
          class="bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600"
        >
          Increment
        </button>
      </div>
    </div>
    
    <!-- Message Section -->
    <div class="border rounded-lg p-6">
      <h2 class="text-xl font-semibold mb-4">Message State</h2>
      <div class="space-y-4">
        <input 
          type="text" 
          value={message}
          oninput={updateMessage}
          class="w-full border rounded px-3 py-2"
        />
        <div class="font-mono text-sm">
          Current: {message}
        </div>
      </div>
    </div>
    
    <!-- Todo List Section -->
    <div class="border rounded-lg p-6 col-span-2">
      <h2 class="text-xl font-semibold mb-4">Array State (Todo List)</h2>
      
      <div class="mb-4 text-sm font-mono">
        Stats: Total: {stats.total}, Completed: {stats.completed}, Pending: {stats.pending}
      </div>
      
      <div class="space-y-2 mb-4">
        {#each items as item (item.id)}
          <div class="flex items-center space-x-2">
            <input 
              type="checkbox" 
              checked={item.done}
              onchange={() => toggleItem(item.id)}
              class="w-4 h-4"
            />
            <span class:line-through={item.done}>
              {item.text}
            </span>
          </div>
        {/each}
      </div>
      
      <button 
        onclick={addItem}
        class="bg-green-500 text-white px-4 py-2 rounded hover:bg-green-600"
      >
        Add Item
      </button>
    </div>
  </div>
  
  <!-- Debug Info -->
  <div class="mt-8 p-4 bg-gray-100 rounded">
    <h3 class="font-semibold mb-2">Component Info</h3>
    <div class="font-mono text-xs">
      <div>ID: {componentId}</div>
      <div>Type: {componentType}</div>
      <div>Check console for [SDP] events</div>
    </div>
  </div>
</div>

{@debug count, message, items}