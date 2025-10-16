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
 * Show error message (safe, auto-escapes HTML)
 * @param {string} message - Error message to display
 * @param {Object} opts - Options
 * @param {string} opts.type - Display type: "status" (temporary, default) or "banner" (persistent)
 */
function showError(message, opts = {}) {
  const { type = "status" } = opts;

  if (type === "banner") {
    // Persistent error banner (dismissable)
    const banner = document.getElementById("errorBanner");
    const messageEl = document.getElementById("errorMessage");
    messageEl.textContent = message; // Safe, auto-escapes
    banner.classList.add("visible");
  } else {
    // Temporary status div (cleared by SSE updates)
    const status = document.getElementById("status");
    status.innerHTML = "";
    const span = document.createElement("span");
    span.className = "error";
    span.textContent = message; // Safe, auto-escapes
    status.appendChild(span);
  }
}

/**
 * Show general message in status div (safe, auto-escapes HTML)
 * @param {string} message - Message to display
 * @param {Object} opts - Options
 * @param {string} opts.className - CSS class for styling (e.g., "connected", "error")
 */
function showMessage(message, opts = {}) {
  const { className = "" } = opts;
  const status = document.getElementById("status");

  if (className) {
    status.innerHTML = "";
    const span = document.createElement("span");
    span.className = className;
    span.textContent = message; // Safe, auto-escapes
    status.appendChild(span);
  } else {
    status.textContent = message; // Safe, auto-escapes
  }
}

// Global lock to prevent concurrent operations
let globalOperationInProgress = false;

/**
 * Disable button during async operation, re-enable after
 * Also prevents any other button operations while one is in progress
 */
async function withButtonLock(buttonId, asyncFn) {
  const btn = document.getElementById(buttonId);
  if (!btn) return;

  // Prevent concurrent operations
  if (globalOperationInProgress) {
    console.log(`[WebTap] Operation already in progress, ignoring ${buttonId}`);
    return;
  }

  const wasDisabled = btn.disabled;
  btn.disabled = true;
  globalOperationInProgress = true;

  try {
    await asyncFn();
  } finally {
    btn.disabled = wasDisabled;
    globalOperationInProgress = false;
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
  console.log("[WebTap] Connecting to SSE stream...");

  // Close existing connection
  if (eventSource) {
    eventSource.close();
    eventSource = null;
  }

  eventSource = new EventSource(`${API_BASE}/events`);

  eventSource.onopen = () => {
    console.log("[WebTap] SSE connected");
    webtapAvailable = true;
    loadPages(); // Load pages when connection established
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
    console.log("[WebTap] Connection failed or lost");
    webtapAvailable = false;

    // Close the connection to stop auto-reconnect
    if (eventSource) {
      eventSource.close();
      eventSource = null;
    }

    state.connected = false;

    // Show error with reconnect button in status
    const status = document.getElementById("status");
    status.innerHTML = "";

    const errorSpan = document.createElement("span");
    errorSpan.className = "error";
    errorSpan.textContent = "Error: WebTap server not running";

    const reconnectBtn = document.createElement("button");
    reconnectBtn.id = "reconnectBtn";
    reconnectBtn.textContent = "Reconnect";
    reconnectBtn.style.marginLeft = "10px";
    reconnectBtn.style.padding = "2px 8px";
    reconnectBtn.style.cursor = "pointer";
    reconnectBtn.onclick = () => {
      showMessage("Connecting...");
      connectSSE();
    };

    status.appendChild(errorSpan);
    status.appendChild(document.createTextNode(" "));
    status.appendChild(reconnectBtn);

    // Clear page list without duplicate error
    document.getElementById("pageList").innerHTML =
      "<option disabled>Select a page</option>";

    // Don't call renderUI() - it would overwrite the reconnect button
  };
}

// ==================== UI Rendering ====================

function renderUI(state) {
  // Error banner
  updateErrorBanner(state.error);

  // Connection status
  if (state.connected && state.page) {
    const status = document.getElementById("status");
    status.innerHTML = "";
    const connectedSpan = document.createElement("span");
    connectedSpan.className = "connected";
    connectedSpan.textContent = "Connected";
    status.appendChild(connectedSpan);
    status.appendChild(document.createTextNode(` - Events: ${state.events.total}`));
  } else if (!state.connected) {
    showMessage("Not connected");
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
      "<option disabled>Select a page</option>";
    return;
  }

  const info = await api("/info");

  if (info.error) {
    document.getElementById("pageList").innerHTML =
      "<option disabled>Unable to load pages</option>";
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

document.getElementById("reloadPages").onclick = () => {
  loadPages();
};

document.getElementById("connect").onclick = debounce(async () => {
  await withButtonLock("connect", async () => {
    const select = document.getElementById("pageList");
    const selectedPageId = select.value;

    if (!selectedPageId) {
      showError("Note: Please select a page");
      return;
    }

    try {
      const result = await api("/connect", "POST", { page_id: selectedPageId });

      if (result.error) {
        showError(`Error: ${result.error}`);
      }
      // State update will come via SSE
    } catch (e) {
      console.error("[WebTap] Connect failed:", e);
      showError("Error: Connection failed");
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
      showError("Error: Disconnect failed");
    }
  });
}, 300);

document.getElementById("clear").onclick = debounce(async () => {
  await withButtonLock("clear", async () => {
    try {
      await api("/clear", "POST");
      // State update will come via SSE
    } catch (e) {
      console.error("[WebTap] Clear failed:", e);
      showError("Error: Failed to clear events");
    }
  });
}, 300);

// ==================== Fetch Interception ====================

document.getElementById("fetchToggle").onclick = async () => {
  if (!state.connected) {
    showError("Required: Connect to a page first");
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
    // Check if still connected before CDP operations
    if (!state.connected) {
      showError("Error: Not connected to a page");
      return;
    }

    const previousState = state.browser.inspect_active;

    try {
      const result = await api(
        previousState ? "/browser/stop-inspect" : "/browser/start-inspect",
        "POST",
      );

      if (result.error) {
        throw new Error(result.error);
      }
      // SSE will send updated state
    } catch (e) {
      console.error("[WebTap] Selection toggle failed:", e);
      showError(`Error: ${e.message}`);
    }
  });
}, 300);

document.getElementById("clearSelections").onclick = debounce(async () => {
  await withButtonLock("clearSelections", async () => {
    try {
      await api("/browser/clear", "POST");
      // State update will come via SSE
    } catch (e) {
      console.error("[WebTap] Clear selections failed:", e);
      showError("Error: Failed to clear selections");
    }
  });
}, 300);

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

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  // Refresh when tab finishes loading (title/URL changed)
  if (changeInfo.status === "complete") {
    debouncedLoadPages();
  }
});

// ==================== Initialization ====================

// Connect to SSE stream on load (will show error if server down)
connectSSE();
