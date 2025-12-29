/**
 * Extension-side Fetch Capture
 *
 * Uses chrome.debugger API to intercept response bodies at the extension level
 * for near-zero latency capture. Bodies are pushed to the daemon asynchronously.
 */

let client = null;
let activeTargets = new Map(); // tabId -> target (e.g., "9222:abc123")

/**
 * Initialize capture module with WebTap client
 * @param {WebTapClient} c - WebTap client instance
 */
export function init(c) {
  client = c;

  // Listen for debugger events
  chrome.debugger.onEvent.addListener(handleDebuggerEvent);

  // Clean up when debugger detaches
  chrome.debugger.onDetach.addListener(handleDebuggerDetach);
}

/**
 * Update capture state based on SSE state
 * @param {Object} state - Current WebTap state from SSE
 */
export function update(state) {
  const captureEnabled = state.fetch?.capture_enabled;

  if (captureEnabled) {
    attachToConnectedTabs(state.connections || []);
  } else {
    detachAll();
  }
}

/**
 * Attach debugger to all connected tabs for capture
 * @param {Array} connections - List of active connections from state
 */
async function attachToConnectedTabs(connections) {
  // Query tabs once and build URL lookup map
  let urlToTabId;
  try {
    const tabs = await chrome.tabs.query({});
    urlToTabId = new Map(tabs.map(t => [t.url, t.id]));
  } catch {
    return; // Can't query tabs
  }

  // Attach to all connections in parallel
  const attachPromises = connections
    .filter(conn => conn.url && urlToTabId.has(conn.url))
    .map(conn => {
      const tabId = urlToTabId.get(conn.url);
      if (activeTargets.has(tabId)) return null; // Already attached
      return attachDebugger(tabId, conn.target).catch(err => {
        console.error(`[WebTap Capture] Failed to attach to tab ${tabId}:`, err);
      });
    })
    .filter(Boolean);

  await Promise.all(attachPromises);
}

/**
 * Attach debugger to a specific tab
 * @param {number} tabId - Chrome tab ID
 * @param {string} target - WebTap target ID
 */
async function attachDebugger(tabId, target) {
  return new Promise((resolve, reject) => {
    chrome.debugger.attach({ tabId }, "1.3", () => {
      if (chrome.runtime.lastError) {
        reject(new Error(chrome.runtime.lastError.message));
        return;
      }

      // Enable Fetch domain at response stage
      chrome.debugger.sendCommand({ tabId }, "Fetch.enable", {
        patterns: [{ requestStage: "Response" }]
      }, () => {
        if (chrome.runtime.lastError) {
          chrome.debugger.detach({ tabId });
          reject(new Error(chrome.runtime.lastError.message));
          return;
        }

        activeTargets.set(tabId, target);
        console.log(`[WebTap Capture] Attached to tab ${tabId} (${target})`);
        resolve();
      });
    });
  });
}

/**
 * Detach debugger from all active targets
 */
function detachAll() {
  for (const tabId of activeTargets.keys()) {
    try {
      chrome.debugger.detach({ tabId });
    } catch {
      // Already detached
    }
  }
  activeTargets.clear();
}

/**
 * Handle debugger events
 * @param {Object} source - Debugger source { tabId }
 * @param {string} method - CDP event method name
 * @param {Object} params - Event parameters
 */
function handleDebuggerEvent(source, method, params) {
  if (method !== "Fetch.requestPaused") return;
  if (!params.responseStatusCode) return; // Only response stage

  handlePausedResponse(source.tabId, params);
}

/**
 * Handle a paused response - capture body and continue
 * @param {number} tabId - Chrome tab ID
 * @param {Object} params - Fetch.requestPaused params
 */
async function handlePausedResponse(tabId, params) {
  const target = activeTargets.get(tabId);
  if (!target) {
    // Not our tab, just continue
    chrome.debugger.sendCommand({ tabId }, "Fetch.continueRequest", {
      requestId: params.requestId
    });
    return;
  }

  // Get response body
  chrome.debugger.sendCommand(
    { tabId },
    "Fetch.getResponseBody",
    { requestId: params.requestId },
    (result) => {
      // Continue request immediately (no latency)
      chrome.debugger.sendCommand({ tabId }, "Fetch.continueRequest", {
        requestId: params.requestId
      });

      // Push body to daemon async (non-blocking)
      if (result?.body && client) {
        client.call("fetch.pushBody", {
          request_id: params.requestId,
          target: target,
          body: result.body,
          base64_encoded: result.base64Encoded || false
        }).catch(err => {
          console.error("[WebTap Capture] Failed to push body:", err);
        });
      }
    }
  );
}

/**
 * Handle debugger detach
 * @param {Object} source - Debugger source { tabId }
 * @param {string} reason - Detach reason
 */
function handleDebuggerDetach(source, reason) {
  if (activeTargets.has(source.tabId)) {
    console.log(`[WebTap Capture] Detached from tab ${source.tabId}: ${reason}`);
    activeTargets.delete(source.tabId);
  }
}
