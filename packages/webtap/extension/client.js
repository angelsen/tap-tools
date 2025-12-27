/**
 * WebTap JSON-RPC 2.0 Client
 *
 * Handles:
 * - JSON-RPC 2.0 request/response format
 * - Automatic epoch tracking from responses
 * - SSE state synchronization
 * - Dynamic port discovery
 * - Debug logging with correlation IDs
 */

// Port discovery constants
const BASE_DAEMON_PORT = 37650;
const MAX_PORT_TRIES = 10;

class WebTapClient {
  /**
   * Discover the daemon port (cached first, then scan)
   * @returns {Promise<number|null>} Daemon port if found, null otherwise
   */
  static async discoverDaemon() {
    // Try cached port first
    try {
      const cached = await chrome.storage.local.get('daemonPort');
      if (cached.daemonPort) {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 500);
        const response = await fetch(`http://localhost:${cached.daemonPort}/health`, {
          signal: controller.signal
        });
        clearTimeout(timeoutId);
        if (response.ok) {
          return cached.daemonPort;
        }
      }
    } catch {
      // Cached port stale or unavailable
    }

    // Scan for daemon
    for (let i = 0; i < MAX_PORT_TRIES; i++) {
      const port = BASE_DAEMON_PORT + i;
      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 500);
        const response = await fetch(`http://localhost:${port}/health`, {
          signal: controller.signal
        });
        clearTimeout(timeoutId);
        if (response.ok) {
          // Cache for next time
          await chrome.storage.local.set({ daemonPort: port });
          return port;
        }
      } catch {
        // Port not available
      }
    }
    return null;
  }

  /**
   * Retry daemon discovery with exponential backoff
   * @param {number} maxRetries - Maximum number of retries (default 3)
   * @returns {Promise<number|null>} Port if found, null if all retries exhausted
   */
  static async discoverDaemonWithRetry(maxRetries = 3) {
    const delays = [500, 1000, 2000];

    for (let attempt = 0; attempt <= maxRetries; attempt++) {
      const port = await WebTapClient.discoverDaemon();
      if (port !== null) {
        return port;
      }

      if (attempt < maxRetries) {
        console.log(`[WebTap] Daemon not found, retry ${attempt + 1}/${maxRetries} in ${delays[attempt]}ms`);
        await new Promise(resolve => setTimeout(resolve, delays[attempt]));
      }
    }

    console.log('[WebTap] Daemon discovery failed after retries');
    return null;
  }

  /**
   * Create a client with auto-discovered port
   * @returns {Promise<WebTapClient|null>} Client instance if daemon found, null otherwise
   */
  static async create() {
    const port = await WebTapClient.discoverDaemonWithRetry();
    if (port === null) {
      return null;
    }
    return new WebTapClient(`http://localhost:${port}`);
  }

  /**
   * @param {string} baseUrl - Base URL for WebTap daemon (default: http://localhost:37650)
   */
  constructor(baseUrl = "http://localhost:37650") {
    this.baseUrl = baseUrl;
    this.debug = false;

    // State synchronized from SSE
    this.state = {
      connectionState: "disconnected",
      epoch: 0,
      connected: false,
      connections: [],
      events: { total: 0 },
      fetch: { enabled: false, paused_count: 0 },
      filters: { enabled: [], disabled: [] },
      browser: { inspect_active: false, selections: {}, prompt: "", pending_count: 0 },
      error: null
    };

    // Event listeners
    this._listeners = new Map();

    // SSE connection
    this._eventSource = null;
  }

  /**
   * Call an RPC method
   * @param {string} method - RPC method name
   * @param {Object} params - Method parameters
   * @param {Object} options - Call options { timeout: number }
   * @returns {Promise<any>} Method result
   * @throws {Error} RPC error with .code, .message, .data properties
   */
  async call(method, params = {}, options = {}) {
    const id = this._generateId();
    const timeout = options.timeout || 30000;

    const request = {
      jsonrpc: "2.0",
      method,
      params,
      id,
      epoch: this.state.epoch
    };

    if (this.debug) {
      console.log(`[WebTap RPC →] ${id}: ${method}`, params);
    }

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), timeout);

      const response = await fetch(`${this.baseUrl}/rpc`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-webtap-client-type": "extension",
          "x-webtap-version": chrome.runtime.getManifest().version,
          "x-webtap-context": "sidepanel"
        },
        body: JSON.stringify(request),
        signal: controller.signal
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();

      // Update epoch from response
      if (data.epoch !== undefined) {
        this.state.epoch = data.epoch;
      }

      if (this.debug) {
        console.log(`[WebTap RPC ←] ${id}:`, data.result || data.error);
      }

      // Handle RPC error
      if (data.error) {
        // Handle STALE_EPOCH with automatic retry
        if (data.error.code === "STALE_EPOCH" && !options._isRetry) {
          // Wait for next SSE state update
          await this._waitForStateUpdate();
          // Retry once with _isRetry flag
          return this.call(method, params, { ...options, _isRetry: true });
        }

        const err = new Error(data.error.message);
        err.code = data.error.code;
        err.data = data.error.data;
        throw err;
      }

      return data.result;

    } catch (err) {
      if (err.name === "AbortError") {
        throw new Error(`RPC timeout after ${timeout}ms`);
      }
      throw err;
    }
  }

  async _waitForStateUpdate(timeout = 2000) {
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.off("state", handler);
        reject(new Error("State update timeout after STALE_EPOCH"));
      }, timeout);

      const handler = () => {
        clearTimeout(timer);
        this.off("state", handler);
        resolve();
      };

      this.on("state", handler);
    });
  }

  /**
   * Check if a method can be called in current state
   * @param {string} method - RPC method name
   * @returns {boolean} True if method is allowed
   */
  canCall(method) {
    const state = this.state.connectionState;

    // Methods that work in any state
    const anyState = ["pages", "status", "filters.status", "errors.dismiss"];
    if (anyState.includes(method)) return true;

    // connect works in any state except connecting (multi-target support)
    if (method === "connect") {
      return state !== "connecting";
    }

    // Methods that need connected or inspecting
    const connectedMethods = [
      "disconnect", "clear",
      "browser.startInspect", "browser.clear",
      "fetch.enable", "fetch.disable", "fetch.resume", "fetch.fail", "fetch.fulfill",
      "network", "request", "console",
      "filters.enable", "filters.disable", "filters.enableAll", "filters.disableAll",
      "cdp"
    ];
    if (connectedMethods.includes(method)) {
      return state === "connected" || state === "inspecting";
    }

    // browser.startInspect only works in connected
    if (method === "browser.startInspect") {
      return state === "connected";
    }

    // browser.stopInspect only works in inspecting
    if (method === "browser.stopInspect") {
      return state === "inspecting";
    }

    // Connecting state blocks everything
    if (state === "connecting") {
      return false;
    }

    return true;
  }

  /**
   * Connect to SSE stream for state updates
   */
  connect() {
    if (this._eventSource) {
      this._eventSource.close();
    }

    this._eventSource = new EventSource(`${this.baseUrl}/events/stream`);

    this._eventSource.onmessage = (event) => {
      try {
        const state = JSON.parse(event.data);
        const previousState = this.state;
        this.state = structuredClone(state);
        this._emit("state", this.state, previousState);

        if (this.debug) {
          console.log("[WebTap SSE]", state);
        }
      } catch (err) {
        console.error("[WebTap] SSE parse error:", err);
      }
    };

    this._eventSource.onerror = (err) => {
      console.error("[WebTap] SSE connection error");
      this._emit("error", err);
    };

    if (this.debug) {
      console.log("[WebTap] SSE connected");
    }
  }

  /**
   * Disconnect from SSE stream
   */
  disconnect() {
    if (this._eventSource) {
      this._eventSource.close();
      this._eventSource = null;

      if (this.debug) {
        console.log("[WebTap] SSE disconnected");
      }
    }
  }

  /**
   * Register event listener
   * @param {string} event - Event name ("state", "error")
   * @param {Function} callback - Event callback
   */
  on(event, callback) {
    if (!this._listeners.has(event)) {
      this._listeners.set(event, []);
    }
    this._listeners.get(event).push(callback);
  }

  /**
   * Remove event listener
   * @param {string} event - Event name
   * @param {Function} callback - Event callback to remove
   */
  off(event, callback) {
    const callbacks = this._listeners.get(event);
    if (callbacks) {
      const index = callbacks.indexOf(callback);
      if (index !== -1) {
        callbacks.splice(index, 1);
      }
    }
  }

  /**
   * Generate correlation ID
   * @private
   */
  _generateId() {
    return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  }

  /**
   * Emit event to listeners
   * @private
   */
  _emit(event, data, extra) {
    const callbacks = this._listeners.get(event);
    if (callbacks) {
      callbacks.forEach(cb => cb(data, extra));
    }
  }
}

// ES6 export
export { WebTapClient };
