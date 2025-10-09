// WebTap Side Panel - SSE-based real-time UI
// Clean break refactor: polling removed, SSE for all state updates

console.log("[WebTap] Side panel loaded");

// ==================== Configuration ====================

const API_BASE = "http://localhost:8765";

// ==================== Utility Functions ====================

/**
 * Debounce function calls to prevent rapid-fire execution
 */
function debounce(fn, delay) {
  let timeout;
  return function (...args) {
    clearTimeout(timeout);
    timeout = setTimeout(() => fn.apply(this, args), delay);
  };
}

/**
 * Disable button during async operation, re-enable after
 */
async function withButtonLock(buttonId, asyncFn) {
  const btn = document.getElementById(buttonId);
  if (!btn) return;

  const wasDisabled = btn.disabled;
  btn.disabled = true;

  try {
    await asyncFn();
  } finally {
    btn.disabled = wasDisabled;
  }
}

// ==================== API Helper ====================

async function api(endpoint, method = "GET", body = null) {
  try {
    const opts = {
      method,
      signal: AbortSignal.timeout(3000),
    };
    if (body) {
      opts.headers = { "Content-Type": "application/json" };
      opts.body = JSON.stringify(body);
    }
    const resp = await fetch(`${API_BASE}${endpoint}`, opts);
    if (!resp.ok) {
      return { error: `HTTP ${resp.status}: ${resp.statusText}` };
    }
    return await resp.json();
  } catch (e) {
    if (e.name === "AbortError") {
      return { error: "WebTap not responding (timeout)" };
    }
    if (e.message.includes("Failed to fetch")) {
      return { error: "WebTap not running" };
    }
    return { error: e.message };
  }
}

// ==================== State Management ====================

let state = {
  connected: false,
  page: null,
  events: { total: 0 },
  fetch: { enabled: false, paused_count: 0 },
  filters: { enabled: [], disabled: [] },
  browser: { inspect_active: false, selections: {}, prompt: "" },
};

let eventSource = null;

// ==================== SSE Connection ====================

let webtapAvailable = false;

function connectSSE() {
  // Don't log if we already know server is down
  if (webtapAvailable) {
    console.log("[WebTap] Connecting to SSE stream...");
  }

  // Close existing connection
  if (eventSource) {
    eventSource.close();
    eventSource = null;
  }

  // Don't try to connect if server is known to be down
  if (!webtapAvailable) {
    return;
  }

  eventSource = new EventSource(`${API_BASE}/events`);

  eventSource.onopen = () => {
    console.log("[WebTap] SSE connected");
    webtapAvailable = true;
    updateConnectionStatus(true);
  };

  eventSource.onmessage = (event) => {
    try {
      const newState = JSON.parse(event.data);

      // Detect connection state changes
      const connectionChanged =
        state.connected !== newState.connected ||
        state.page?.id !== newState.page?.id;

      // Only log first state update or significant changes
      if (!state.connected || state.connected !== newState.connected) {
        console.log("[WebTap] State update received");
      }

      // Update local state
      state = newState;

      // Render UI
      renderUI(state);

      // Refresh page list to highlight connected page
      if (connectionChanged) {
        loadPages();
      }

      // Update badges if selections changed
      updateBadges(state.browser.selections);
    } catch (e) {
      console.error("[WebTap] Failed to parse SSE message:", e);
    }
  };

  eventSource.onerror = (error) => {
    // Only log once when connection is lost
    if (webtapAvailable) {
      console.log("[WebTap] Server connection lost");
      webtapAvailable = false;
      updateConnectionStatus(false);
    }

    // Close the connection to stop auto-reconnect
    if (eventSource) {
      eventSource.close();
      eventSource = null;
    }

    state.connected = false;
    renderUI(state);
  };
}

function updateConnectionStatus(connected) {
  const statusEl = document.getElementById("status");
  if (connected) {
    statusEl.innerHTML = "Connected";
  } else {
    statusEl.innerHTML = "Disconnected";
  }
}

// ==================== UI Rendering ====================

function renderUI(state) {
  // Error banner
  updateErrorBanner(state.error);

  // Connection status
  if (state.connected && state.page) {
    document.getElementById("status").innerHTML =
      `<span class="connected">Connected</span> - Events: ${state.events.total}`;
  } else if (!state.connected) {
    document.getElementById("status").innerHTML = "Not connected";
  }

  // Fetch interception status
  updateFetchStatus(state.fetch.enabled, state.fetch.paused_count);

  // Filter status
  updateFiltersUI(state.filters);

  // Element selection status
  updateSelectionUI(state.browser);

  // Enable/disable buttons
  document.getElementById("connect").disabled = false;
  document.getElementById("fetchToggle").disabled = !state.connected;
}

function updateErrorBanner(error) {
  const banner = document.getElementById("errorBanner");
  const message = document.getElementById("errorMessage");

  if (error && error.message) {
    message.textContent = error.message;
    banner.classList.add("visible");
  } else {
    banner.classList.remove("visible");
  }
}

function updateFetchStatus(enabled, pausedCount = 0) {
  const toggle = document.getElementById("fetchToggle");
  const statusDiv = document.getElementById("fetchStatus");

  if (enabled) {
    toggle.textContent = "Disable Intercept";
    toggle.classList.add("active");
    statusDiv.innerHTML = `<span class="fetch-active">Intercept ON</span> - Paused: ${pausedCount}`;
  } else {
    toggle.textContent = "Enable Intercept";
    toggle.classList.remove("active");
    statusDiv.innerHTML = '<span class="fetch-inactive">Intercept OFF</span>';
  }
}

function updateFiltersUI(filters) {
  const filterList = document.getElementById("filterList");
  const filterStats = document.getElementById("filterStats");

  // Clear existing
  filterList.innerHTML = "";

  // Show enabled/disabled counts
  const enabled = filters.enabled || [];
  const disabled = filters.disabled || [];
  const total = enabled.length + disabled.length;

  filterStats.textContent = `${enabled.length}/${total} categories enabled`;

  // Render enabled categories
  enabled.forEach((cat) => {
    const label = document.createElement("label");
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = true;
    checkbox.dataset.category = cat;
    checkbox.onchange = () => toggleFilter(cat);

    label.appendChild(checkbox);
    label.appendChild(document.createTextNode(cat));
    filterList.appendChild(label);
  });

  // Render disabled categories
  disabled.forEach((cat) => {
    const label = document.createElement("label");
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = false;
    checkbox.dataset.category = cat;
    checkbox.onchange = () => toggleFilter(cat);

    label.appendChild(checkbox);
    label.appendChild(document.createTextNode(cat));
    filterList.appendChild(label);
  });
}

function updateSelectionUI(browser) {
  const selectionButton = document.getElementById("startSelection");
  const selectionCount = document.getElementById("selectionCount");
  const selectionList = document.getElementById("selectionList");
  const selectionStatus = document.getElementById("selectionStatus");

  // Update button state
  if (browser.inspect_active) {
    selectionButton.textContent = "Stop Selection";
    selectionButton.style.background = "#f44336";
    selectionButton.style.color = "white";
  } else {
    selectionButton.textContent = "Start Selection Mode";
    selectionButton.style.background = "";
    selectionButton.style.color = "";
  }

  // Update selection count with progress indicator
  const count = Object.keys(browser.selections || {}).length;
  const pending = browser.pending_count || 0;

  if (pending > 0) {
    selectionCount.textContent = `${count} (Processing: ${pending})`;
    selectionCount.style.color = "#ff9800"; // Orange for processing
  } else {
    selectionCount.textContent = count;
    selectionCount.style.color = "";
  }

  // Show/hide selection status based on whether we have selections
  if (count > 0) {
    selectionStatus.style.display = "block";
  } else {
    selectionStatus.style.display = "none";
  }

  // Update selection list
  selectionList.innerHTML = "";
  Object.entries(browser.selections || {}).forEach(([id, data]) => {
    const div = document.createElement("div");
    div.className = "selection-item";

    const badge = document.createElement("span");
    badge.className = "selection-badge";
    badge.textContent = `#${id}`;

    const preview = document.createElement("span");
    preview.className = "selection-preview";
    const previewData = data.preview || {};
    preview.textContent = `<${previewData.tag}>${previewData.id ? " #" + previewData.id : ""}${previewData.classes && previewData.classes.length ? " ." + previewData.classes.join(".") : ""}`;

    div.appendChild(badge);
    div.appendChild(preview);
    selectionList.appendChild(div);
  });
}

// ==================== Page Management ====================

async function loadPages() {
  if (!webtapAvailable) {
    document.getElementById("pageList").innerHTML =
      "<option disabled>Error: WebTap not running</option>";
    return;
  }

  const info = await api("/info");

  if (info.error) {
    document.getElementById("pageList").innerHTML =
      `<option disabled>${info.error === "WebTap not initialized" ? "Error: WebTap not running" : "Warning: Error loading pages"}</option>`;
    return;
  }

  const pages = info.pages || [];
  const select = document.getElementById("pageList");
  select.innerHTML = "";

  if (pages.length === 0) {
    select.innerHTML = "<option disabled>Empty: No pages available</option>";
  } else {
    const currentPageId = state.page ? state.page.id : null;

    pages.forEach((page, index) => {
      const option = document.createElement("option");
      option.value = page.id;

      const title = page.title || "Untitled";
      const shortTitle =
        title.length > 50 ? title.substring(0, 47) + "..." : title;

      // Highlight connected page
      if (page.id === currentPageId) {
        option.style.fontWeight = "bold";
        option.style.color = "#080";
        option.selected = true;
      }

      option.textContent = `${index}: ${shortTitle}`;
      select.appendChild(option);
    });
  }
}

// Debounced version for automatic refresh on tab events
const debouncedLoadPages = debounce(loadPages, 500);

document.getElementById("connect").onclick = debounce(async () => {
  await withButtonLock("connect", async () => {
    const select = document.getElementById("pageList");
    const selectedPageId = select.value;

    if (!selectedPageId) {
      document.getElementById("status").innerHTML =
        '<span class="error">Note: Please select a page</span>';
      return;
    }

    try {
      const result = await api("/connect", "POST", { page_id: selectedPageId });

      if (result.error) {
        document.getElementById("status").innerHTML =
          `<span class="error">Error: ${result.error}</span>`;
      }
      // State update will come via SSE
    } catch (e) {
      console.error("[WebTap] Connect failed:", e);
      document.getElementById("status").innerHTML =
        '<span class="error">Error: Connection failed</span>';
    }
  });
}, 300);

document.getElementById("disconnect").onclick = debounce(async () => {
  await withButtonLock("disconnect", async () => {
    try {
      await api("/disconnect", "POST");
      // State update will come via SSE
    } catch (e) {
      console.error("[WebTap] Disconnect failed:", e);
      document.getElementById("status").innerHTML =
        '<span class="error">Error: Disconnect failed</span>';
    }
  });
}, 300);

document.getElementById("clear").onclick = async () => {
  try {
    await api("/clear", "POST");
    // State update will come via SSE
  } catch (e) {
    console.error("[WebTap] Clear failed:", e);
  }
};

// ==================== Fetch Interception ====================

document.getElementById("fetchToggle").onclick = async () => {
  if (!state.connected) {
    document.getElementById("status").innerHTML =
      '<span class="error">Required: Connect to a page first</span>';
    return;
  }

  const newState = !state.fetch.enabled;
  const responseStage = document.getElementById("responseStage").checked;

  try {
    await api("/fetch", "POST", {
      enabled: newState,
      response_stage: responseStage,
    });
    // State update will come via SSE
  } catch (e) {
    console.error("[WebTap] Fetch toggle failed:", e);
  }
};

// ==================== Filter Management ====================

async function toggleFilter(category) {
  try {
    await api(`/filters/toggle/${category}`, "POST");
    // State update will come via SSE
  } catch (e) {
    console.error("[WebTap] Filter toggle failed:", e);
  }
}

document.getElementById("enableAllFilters").onclick = async () => {
  try {
    await api("/filters/enable-all", "POST");
    // State update will come via SSE
  } catch (e) {
    console.error("[WebTap] Enable all filters failed:", e);
  }
};

document.getElementById("disableAllFilters").onclick = async () => {
  try {
    await api("/filters/disable-all", "POST");
    // State update will come via SSE
  } catch (e) {
    console.error("[WebTap] Disable all filters failed:", e);
  }
};

// ==================== Element Selection (CDP-based) ====================

document.getElementById("startSelection").onclick = debounce(async () => {
  await withButtonLock("startSelection", async () => {
    // Optimistic update: flip state immediately for instant UI feedback
    const previousState = state.browser.inspect_active;
    state.browser.inspect_active = !previousState;
    updateSelectionUI(state.browser);

    try {
      const result = await api(
        previousState ? "/browser/stop-inspect" : "/browser/start-inspect",
        "POST",
      );

      if (result.error) {
        throw new Error(result.error);
      }
      // SSE will confirm the change
    } catch (e) {
      console.error("[WebTap] Selection toggle failed:", e);
      // Rollback optimistic update on failure
      state.browser.inspect_active = previousState;
      updateSelectionUI(state.browser);
      document.getElementById("status").innerHTML =
        `<span class="error">Warning: ${e.message}</span>`;
    }
  });
}, 300);

document.getElementById("clearSelections").onclick = async () => {
  try {
    await api("/browser/clear", "POST");
    // State update will come via SSE
  } catch (e) {
    console.error("[WebTap] Clear selections failed:", e);
  }
};

// Removed submit flow - selections accessed via @webtap:webtap://selections resource

// ==================== Error Handling ====================

document.getElementById("dismissError").onclick = async () => {
  try {
    await api("/errors/dismiss", "POST");
    // State update will come via SSE
  } catch (e) {
    console.error("[WebTap] Dismiss error failed:", e);
  }
};

// ==================== Badge Rendering ====================

async function updateBadges(selections) {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

  if (!tab || tab.url.startsWith("chrome://") || tab.url.startsWith("about:")) {
    return; // Can't inject into chrome:// or about:// pages
  }

  try {
    // First check if content script is ready
    await chrome.tabs.sendMessage(tab.id, { action: "ping" });

    // If ping succeeds, send badge update
    await chrome.tabs.sendMessage(tab.id, {
      action: "updateBadges",
      selections: selections,
    });
  } catch (e) {
    // Content script not ready - inject it first
    try {
      await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        files: ["content.js"],
      });

      // Wait a moment for script to initialize
      await new Promise((resolve) => setTimeout(resolve, 100));

      // Try sending badges again
      await chrome.tabs.sendMessage(tab.id, {
        action: "updateBadges",
        selections: selections,
      });
    } catch (injectError) {
      // Page doesn't support content scripts (chrome://, extensions, etc)
      console.debug("[WebTap] Cannot inject content script on this page");
    }
  }
}

// ==================== Health Check Polling ====================

async function checkHealth() {
  try {
    const response = await fetch(`${API_BASE}/health`, {
      // Add timeout to fail faster
      signal: AbortSignal.timeout(1000),
    });
    if (response.ok) {
      // WebTap is alive
      if (!webtapAvailable) {
        console.log("[WebTap] Server started - connecting...");
        webtapAvailable = true;
        connectSSE();
        loadPages(); // Refresh page list when server comes online
      }
    }
  } catch (e) {
    // Server is down - this is expected, not an error
    // Only update UI if state changed
    if (webtapAvailable) {
      console.log("[WebTap] Server stopped");
      webtapAvailable = false;
      document.getElementById("status").innerHTML =
        '<span class="error">Error: WebTap not running</span>';
      document.getElementById("pageList").innerHTML =
        "<option disabled>Run: Start WebTap REPL and run server()</option>";
    }
  }
}

// ==================== Tab Event Listeners ====================

// Auto-refresh page list on tab changes (aggressive mode)
chrome.tabs.onActivated.addListener(() => {
  debouncedLoadPages();
});

chrome.tabs.onRemoved.addListener(() => {
  debouncedLoadPages();
});

chrome.tabs.onCreated.addListener(() => {
  debouncedLoadPages();
});

chrome.tabs.onMoved.addListener(() => {
  debouncedLoadPages();
});

// ==================== Initialization ====================

// Check health first to see if server is running (will auto-load pages when available)
checkHealth();

// Poll health every 3 seconds (will connect SSE when server starts)
setInterval(checkHealth, 3000);
