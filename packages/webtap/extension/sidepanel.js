// WebTap Side Panel - Clean Break Refactor
// SSE-based real-time UI with tab navigation

console.log("[WebTap] Side panel loaded");

// ==================== Configuration ====================

const API_BASE = "http://localhost:8765";

// ==================== Theme Management ====================

function updateThemeButton() {
  const btn = document.getElementById("themeToggle");
  if (!btn) return;
  const theme = document.documentElement.dataset.theme;
  btn.textContent = theme === "light" ? "Light" : theme === "dark" ? "Dark" : "Auto";
}

function initTheme() {
  const saved = localStorage.getItem("webtap-theme");
  if (saved) {
    document.documentElement.dataset.theme = saved;
  }
  updateThemeButton();
}

function toggleTheme() {
  const current = document.documentElement.dataset.theme;
  let next;
  if (!current) {
    next = "light";
  } else if (current === "light") {
    next = "dark";
  } else {
    next = null;
  }

  if (next) {
    document.documentElement.dataset.theme = next;
    localStorage.setItem("webtap-theme", next);
  } else {
    delete document.documentElement.dataset.theme;
    localStorage.removeItem("webtap-theme");
  }
  updateThemeButton();
}

initTheme();

// ==================== Tab Management ====================

let activeTab = localStorage.getItem("webtap-tab") || "intercept";

function initTabs() {
  const tabButtons = document.querySelectorAll(".tab-button");
  const tabContents = document.querySelectorAll(".tab-content");

  // Set initial state
  tabButtons.forEach((btn) => {
    const tab = btn.dataset.tab;
    btn.classList.toggle("active", tab === activeTab);
    btn.setAttribute("aria-selected", tab === activeTab);
  });

  tabContents.forEach((content) => {
    content.classList.toggle("active", content.dataset.tab === activeTab);
  });

  // Add click handlers
  tabButtons.forEach((btn) => {
    btn.addEventListener("click", () => switchTab(btn.dataset.tab));
  });
}

function switchTab(tabName) {
  if (tabName === activeTab) return;

  activeTab = tabName;
  localStorage.setItem("webtap-tab", tabName);

  document.querySelectorAll(".tab-button").forEach((btn) => {
    const isActive = btn.dataset.tab === tabName;
    btn.classList.toggle("active", isActive);
    btn.setAttribute("aria-selected", isActive);
  });

  document.querySelectorAll(".tab-content").forEach((content) => {
    content.classList.toggle("active", content.dataset.tab === tabName);
  });

  // Refresh network when switching to network tab
  if (tabName === "network" && state.connected) {
    fetchNetwork();
  }
}

// ==================== UI Helpers ====================

const ui = {
  el(tag, opts = {}) {
    const el = document.createElement(tag);
    if (opts.class) el.className = opts.class;
    if (opts.text) el.textContent = opts.text;
    if (opts.title) el.title = opts.title;
    if (opts.onclick) el.onclick = opts.onclick;
    if (opts.attrs) {
      Object.entries(opts.attrs).forEach(([k, v]) => el.setAttribute(k, v));
    }
    if (opts.children) {
      opts.children.forEach((c) => c && el.appendChild(c));
    }
    return el;
  },

  row(className, children) {
    return this.el("div", { class: className, children });
  },

  details(summary, content) {
    const details = this.el("details");
    details.appendChild(this.el("summary", { text: summary }));
    if (typeof content === "string") {
      const pre = this.el("pre", { text: content, class: "text-muted" });
      details.appendChild(pre);
    } else {
      details.appendChild(content);
    }
    return details;
  },

  loading(el) {
    el.textContent = "Loading...";
  },

  empty(el, message = null) {
    el.innerHTML = "";
    if (message) {
      el.appendChild(this.el("div", { text: message, class: "text-muted" }));
    }
  },
};

function showError(message, opts = {}) {
  const { type = "status" } = opts;

  if (type === "banner") {
    const banner = document.getElementById("errorBanner");
    const messageEl = document.getElementById("errorMessage");
    messageEl.textContent = message;
    banner.classList.add("visible");
  } else {
    const status = document.getElementById("status");
    status.innerHTML = "";
    const span = document.createElement("span");
    span.className = "error";
    span.textContent = message;
    status.appendChild(span);
  }
}

function showMessage(message, opts = {}) {
  const { className = "" } = opts;
  const status = document.getElementById("status");

  if (className) {
    status.innerHTML = "";
    const span = document.createElement("span");
    span.className = className;
    span.textContent = message;
    status.appendChild(span);
  } else {
    status.textContent = message;
  }
}

// ==================== Operation Lock ====================

let globalOperationInProgress = false;

async function withButtonLock(buttonId, asyncFn) {
  const btn = document.getElementById(buttonId);
  if (!btn) return;

  if (globalOperationInProgress) {
    console.log(`[WebTap] Operation in progress, ignoring ${buttonId}`);
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
let webtapAvailable = false;

let previousHashes = {
  selections: "",
  filters: "",
  fetch: "",
  page: "",
  error: "",
};

function updateFromState(newState) {
  if (!newState) return;

  state = newState;
  updateConnectionStatus(newState);
  updateEventCount(newState.events.total);
  updateButtons(newState.connected);
  updateErrorBanner(newState.error);
  updateFetchStatus(newState.fetch.enabled, newState.fetch.paused_count);
  updateFiltersUI(newState.filters);
  updateSelectionUI(newState.browser);

  previousHashes = {
    selections: newState.selections_hash,
    filters: newState.filters_hash,
    fetch: newState.fetch_hash,
    page: newState.page_hash,
    error: newState.error_hash || "",
  };

  if (newState.connected && activeTab === "network") {
    fetchNetwork();
  }
}

// ==================== SSE Connection ====================

function connectSSE() {
  console.log("[WebTap] Connecting to SSE stream...");

  if (eventSource) {
    eventSource.close();
    eventSource = null;
  }

  eventSource = new EventSource(`${API_BASE}/events/stream`);

  eventSource.onopen = () => {
    console.log("[WebTap] SSE connected");
    webtapAvailable = true;
    loadPages();
  };

  eventSource.onmessage = (event) => {
    try {
      const newState = JSON.parse(event.data);

      const connectionChanged =
        state.connected !== newState.connected ||
        state.page?.id !== newState.page?.id;

      if (!state.connected || state.connected !== newState.connected) {
        console.log("[WebTap] State update received");
      }

      state = newState;

      // Hash-based selective updates
      if (newState.selections_hash !== previousHashes.selections) {
        previousHashes.selections = newState.selections_hash;
        updateSelectionUI(newState.browser);
      }

      if (newState.filters_hash !== previousHashes.filters) {
        previousHashes.filters = newState.filters_hash;
        updateFiltersUI(newState.filters);
      }

      if (newState.fetch_hash !== previousHashes.fetch) {
        previousHashes.fetch = newState.fetch_hash;
        updateFetchStatus(newState.fetch.enabled, newState.fetch.paused_count);
      }

      if (newState.page_hash !== previousHashes.page) {
        previousHashes.page = newState.page_hash;
        updateConnectionStatus(newState);
      }

      updateErrorBanner(newState.error);
      updateEventCount(newState.events.total);
      updateButtons(newState.connected);

      if (connectionChanged) {
        loadPages();
      }

      if (newState.connected && activeTab === "network") {
        fetchNetwork();
      }
    } catch (e) {
      console.error("[WebTap] Failed to parse SSE message:", e);
    }
  };

  eventSource.onerror = () => {
    console.log("[WebTap] Connection failed or lost");
    webtapAvailable = false;

    if (eventSource) {
      eventSource.close();
      eventSource = null;
    }

    state.connected = false;

    const status = document.getElementById("status");
    ui.empty(status);

    status.appendChild(
      ui.row(null, [
        ui.el("span", { class: "error", text: "Error: WebTap server not running" }),
        ui.el("button", {
          text: "Reconnect",
          class: "reconnect-btn",
          onclick: () => {
            showMessage("Connecting...");
            connectSSE();
          },
        }),
      ]),
    );

    document.getElementById("pageList").innerHTML =
      "<option disabled>Select a page</option>";
  };
}

// ==================== Cleanup on Unload ====================

window.addEventListener("beforeunload", () => {
  if (eventSource) {
    eventSource.close();
    eventSource = null;
  }
});

// ==================== UI Rendering ====================

function updateConnectionStatus(state) {
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
}

function updateEventCount(count) {
  const status = document.getElementById("status");
  const connectedSpan = status.querySelector(".connected");
  if (connectedSpan) {
    while (status.lastChild !== connectedSpan) {
      status.removeChild(status.lastChild);
    }
    status.appendChild(document.createTextNode(` - Events: ${count}`));
  }
}

function updateButtons(connected) {
  document.getElementById("connect").disabled = false;
  document.getElementById("fetchToggle").disabled = !connected;
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
    ui.empty(statusDiv);
    statusDiv.appendChild(
      ui.row(null, [
        ui.el("span", { class: "fetch-active", text: "Intercept ON" }),
        ui.el("span", { text: ` - Paused: ${pausedCount}` }),
      ]),
    );
  } else {
    toggle.textContent = "Enable Intercept";
    toggle.classList.remove("active");
    ui.empty(statusDiv);
    statusDiv.appendChild(ui.el("span", { class: "fetch-inactive", text: "Intercept OFF" }));
  }
}

function updateFiltersUI(filters) {
  const filterList = document.getElementById("filterList");
  const filterStats = document.getElementById("filterStats");

  const enabled = filters.enabled || [];
  const disabled = filters.disabled || [];
  const total = enabled.length + disabled.length;

  filterStats.textContent = `${enabled.length}/${total} groups enabled`;
  ui.empty(filterList);

  const createFilterCheckbox = (name, isEnabled) => {
    const checkbox = ui.el("input", {
      attrs: { type: "checkbox", "data-filter": name },
    });
    checkbox.checked = isEnabled;
    checkbox.onchange = () => toggleFilter(name, checkbox);

    const label = ui.el("label", { children: [checkbox] });
    label.appendChild(document.createTextNode(name));
    return label;
  };

  enabled.forEach((name) => filterList.appendChild(createFilterCheckbox(name, true)));
  disabled.forEach((name) => filterList.appendChild(createFilterCheckbox(name, false)));
}

function updateSelectionUI(browser) {
  const selectionButton = document.getElementById("startSelection");
  const selectionCount = document.getElementById("selectionCount");
  const selectionList = document.getElementById("selectionList");
  const selectionStatus = document.getElementById("selectionStatus");

  if (browser.inspect_active) {
    selectionButton.textContent = "Stop Selection";
    selectionButton.classList.add("active-selection");
  } else {
    selectionButton.textContent = "Start Selection Mode";
    selectionButton.classList.remove("active-selection");
  }

  const count = Object.keys(browser.selections || {}).length;
  const pending = browser.pending_count || 0;

  if (pending > 0) {
    selectionCount.textContent = `${count} (Processing: ${pending})`;
    selectionCount.classList.add("processing");
  } else {
    selectionCount.textContent = count;
    selectionCount.classList.remove("processing");
  }

  selectionStatus.classList.toggle("hidden", count === 0);
  ui.empty(selectionList);

  Object.entries(browser.selections || {}).forEach(([id, data]) => {
    const preview = data.preview || {};
    const previewText = `<${preview.tag}>${preview.id ? " #" + preview.id : ""}${
      preview.classes?.length ? " ." + preview.classes.join(".") : ""
    }`;

    selectionList.appendChild(
      ui.row("selection-item", [
        ui.el("span", { class: "selection-badge", text: `#${id}` }),
        ui.el("span", { class: "selection-preview", text: previewText }),
      ]),
    );
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
      const shortTitle = title.length > 50 ? title.substring(0, 47) + "..." : title;

      if (page.id === currentPageId) {
        option.className = "connected";
        option.selected = true;
      }

      option.textContent = `${index}: ${shortTitle}`;
      select.appendChild(option);
    });
  }
}

// ==================== Event Handlers ====================

document.getElementById("reloadPages").onclick = async () => {
  await withButtonLock("reloadPages", loadPages);
};

document.getElementById("connect").onclick = async () => {
  await withButtonLock("connect", async () => {
    const select = document.getElementById("pageList");
    const selectedPageId = select.value;

    if (!selectedPageId) {
      showError("Note: Please select a page");
      return;
    }

    try {
      const result = await api("/connect", "POST", { page_id: selectedPageId });

      if (result.state) {
        updateFromState(result.state);
      }

      if (result.error) {
        showError(`Error: ${result.error}`);
      }
    } catch (e) {
      console.error("[WebTap] Connect failed:", e);
      showError("Error: Connection failed");
    }
  });
};

document.getElementById("disconnect").onclick = async () => {
  await withButtonLock("disconnect", async () => {
    try {
      const result = await api("/disconnect", "POST");

      if (result.state) {
        updateFromState(result.state);
      }

      if (result.error) {
        showError(`Error: ${result.error}`);
      }
    } catch (e) {
      console.error("[WebTap] Disconnect failed:", e);
      showError("Error: Disconnect failed");
    }
  });
};

document.getElementById("clear").onclick = async () => {
  await withButtonLock("clear", async () => {
    try {
      const result = await api("/clear", "POST", { events: true });

      if (result.state) {
        updateFromState(result.state);
      }

      if (result.error) {
        showError(`Error: ${result.error}`);
      }
    } catch (e) {
      console.error("[WebTap] Clear failed:", e);
      showError("Error: Failed to clear events");
    }
  });
};

// ==================== Fetch Interception ====================

document.getElementById("fetchToggle").onclick = async () => {
  await withButtonLock("fetchToggle", async () => {
    if (!state.connected) {
      showError("Required: Connect to a page first");
      return;
    }

    const newState = !state.fetch.enabled;
    const responseStage = document.getElementById("responseStage").checked;

    try {
      const result = await api("/fetch", "POST", {
        enabled: newState,
        response_stage: responseStage,
      });

      if (result.state) {
        updateFromState(result.state);
      }

      if (result.error) {
        showError(`Error: ${result.error}`);
      }
    } catch (e) {
      console.error("[WebTap] Fetch toggle failed:", e);
    }
  });
};

// ==================== Filter Management ====================

async function toggleFilter(name, checkbox) {
  // Disable checkbox during operation
  checkbox.disabled = true;

  try {
    const isEnabled = state.filters.enabled.includes(name);
    const result = await api(`/filters/${isEnabled ? "disable" : "enable"}/${name}`, "POST");

    if (result.state) {
      updateFromState(result.state);
    }
    if (result.error) {
      showError(`Filter toggle failed: ${result.error}`);
      // Revert checkbox on error
      checkbox.checked = isEnabled;
    }
  } catch (e) {
    console.error("[WebTap] Filter toggle failed:", e);
    checkbox.checked = state.filters.enabled.includes(name);
  } finally {
    checkbox.disabled = false;
  }
}

document.getElementById("enableAllFilters").onclick = async () => {
  await withButtonLock("enableAllFilters", async () => {
    const result = await api("/filters/enable-all", "POST");
    if (result.state) {
      updateFromState(result.state);
    }
    if (result.error) {
      showError(`Enable all failed: ${result.error}`);
    }
  });
};

document.getElementById("disableAllFilters").onclick = async () => {
  await withButtonLock("disableAllFilters", async () => {
    const result = await api("/filters/disable-all", "POST");
    if (result.state) {
      updateFromState(result.state);
    }
    if (result.error) {
      showError(`Disable all failed: ${result.error}`);
    }
  });
};

// ==================== Element Selection ====================

document.getElementById("startSelection").onclick = async () => {
  await withButtonLock("startSelection", async () => {
    if (!state.connected) {
      showError("Error: Not connected to a page");
      return;
    }

    try {
      const endpoint = state.browser.inspect_active
        ? "/browser/stop-inspect"
        : "/browser/start-inspect";
      const result = await api(endpoint, "POST");

      if (result.state) {
        updateFromState(result.state);
      }
      if (result.error) {
        showError(`Error: ${result.error}`);
      }
    } catch (e) {
      console.error("[WebTap] Selection toggle failed:", e);
      showError(`Error: ${e.message}`);
    }
  });
};

document.getElementById("clearSelections").onclick = async () => {
  await withButtonLock("clearSelections", async () => {
    try {
      const result = await api("/browser/clear", "POST");
      if (result.state) {
        updateFromState(result.state);
      }
      if (result.error) {
        showError(`Error: ${result.error}`);
      }
    } catch (e) {
      console.error("[WebTap] Clear selections failed:", e);
      showError("Error: Failed to clear selections");
    }
  });
};

// ==================== Error Handling ====================

document.getElementById("dismissError").onclick = async () => {
  await withButtonLock("dismissError", async () => {
    const result = await api("/errors/dismiss", "POST");
    if (result.state) {
      updateFromState(result.state);
    }
  });
};

// ==================== Network Table ====================

let selectedRequestId = null;

async function fetchNetwork() {
  const container = document.getElementById("networkTable");
  const countEl = document.getElementById("networkCount");

  if (!state.connected) {
    ui.empty(container, "Connect to a page to see requests");
    countEl.textContent = "0 requests";
    return;
  }

  const result = await api("/network?limit=50&order=asc");
  if (result.error) {
    showError(`Network fetch failed: ${result.error}`);
    return;
  }

  updateNetworkTable(result.requests || []);

  // Auto-scroll to bottom (newest entries)
  container.scrollTop = container.scrollHeight;
}

function updateNetworkTable(requests) {
  const container = document.getElementById("networkTable");
  const countEl = document.getElementById("networkCount");

  countEl.textContent = `${requests.length} requests`;

  if (requests.length === 0) {
    ui.empty(container, "No requests captured");
    return;
  }

  ui.empty(container);
  requests.forEach((req) => {
    const isError = req.status >= 400;
    const row = ui.row("network-row" + (isError ? " error" : ""), [
      ui.el("span", { class: "network-method", text: req.method || "GET" }),
      ui.el("span", {
        class: "network-status " + (isError ? "error" : "ok"),
        text: String(req.status || "-"),
      }),
      ui.el("span", { class: "network-url", text: req.url || "", title: req.url || "" }),
    ]);
    row.onclick = () => showRequestDetails(req.id);
    container.appendChild(row);
  });
}

function closeRequestDetails() {
  selectedRequestId = null;
  document.getElementById("requestDetails").classList.add("hidden");
}

async function showRequestDetails(id) {
  const detailsEl = document.getElementById("requestDetails");

  if (selectedRequestId === id) {
    closeRequestDetails();
    return;
  }

  const wasHidden = detailsEl.classList.contains("hidden");
  selectedRequestId = id;
  detailsEl.classList.remove("hidden");

  // Only show loading if panel was hidden (avoids flash when switching entries)
  if (wasHidden) {
    ui.loading(detailsEl);
  }

  const result = await api(`/request/${id}`);
  if (result.error) {
    ui.empty(detailsEl, `Error: ${result.error}`);
    return;
  }

  const entry = result.entry;
  ui.empty(detailsEl);

  detailsEl.appendChild(
    ui.row("request-details-header", [
      ui.el("span", { text: `${entry.request?.method || "GET"} ${entry.response?.status || ""}` }),
      ui.el("button", {
        class: "close-btn",
        title: "Close",
        onclick: closeRequestDetails,
      }),
    ]),
  );

  detailsEl.appendChild(
    ui.el("div", {
      text: entry.request?.url || "",
      class: "url-display",
    }),
  );

  if (entry.response?.content?.mimeType) {
    detailsEl.appendChild(
      ui.el("div", {
        text: `Type: ${entry.response.content.mimeType}`,
        class: "text-muted",
      }),
    );
  }

  if (entry.request?.headers) {
    const headerCount = Object.keys(entry.request.headers).length;
    detailsEl.appendChild(
      ui.details(`Request Headers (${headerCount})`, JSON.stringify(entry.request.headers, null, 2)),
    );
  }

  if (entry.response?.headers) {
    const headerCount = Object.keys(entry.response.headers).length;
    detailsEl.appendChild(
      ui.details(
        `Response Headers (${headerCount})`,
        JSON.stringify(entry.response.headers, null, 2),
      ),
    );
  }
}

// ==================== Chrome Tab Listeners ====================

chrome.tabs.onActivated.addListener(() => loadPages());
chrome.tabs.onRemoved.addListener(() => loadPages());
chrome.tabs.onCreated.addListener(() => loadPages());
chrome.tabs.onMoved.addListener(() => loadPages());
chrome.tabs.onUpdated.addListener((tabId, changeInfo) => {
  if (changeInfo.status === "complete") {
    loadPages();
  }
});

// ==================== Initialization ====================

document.getElementById("themeToggle").onclick = toggleTheme;
initTabs();
connectSSE();
