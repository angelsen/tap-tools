console.log("[WebTap] Side panel loaded");

const icons = {
  close: "✕",
  pause: "⏸",
  play: "▶",
  stop: "■",
  error: "⚠",
  success: "✓",
  pending: "○",
  loading: "◌",
  refresh: "↻",
  arrow: "→",
};

const API_BASE = "http://localhost:8765";
const client = new WebTapClient(API_BASE);

const bindings = Bind.connect(client);

const selectionList = new ListRenderer("#selectionList", {
  render: (data, id) => {
    const preview = data.preview || {};
    const previewText = `<${preview.tag}>${preview.id ? " #" + preview.id : ""}${
      preview.classes?.length ? " ." + preview.classes.join(".") : ""
    }`;

    return ui.row("selection-item", [
      ui.el("span", { class: "selection-badge", text: `#${id}` }),
      ui.el("span", { class: "selection-preview", text: previewText }),
    ]);
  },
});

function updateThemeButton() {
  const btn = document.getElementById("themeToggle");
  if (!btn) return;
  const theme = document.documentElement.dataset.theme;
  btn.textContent =
    theme === "light" ? "Light" : theme === "dark" ? "Dark" : "Auto";
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

let activeTab = localStorage.getItem("webtap-tab") || "pages";

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
  if (tabName === "network" && client.state.connected) {
    fetchNetwork();
  }
}

function truncateMiddle(str, maxLen) {
  if (!str || str.length <= maxLen) return str;
  const ellipsis = "…";
  const charsToShow = maxLen - ellipsis.length;
  const frontChars = Math.ceil(charsToShow / 2);
  const backChars = Math.floor(charsToShow / 2);
  return str.slice(0, frontChars) + ellipsis + str.slice(-backChars);
}

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

function updateHeaderStatus(text, state = "disconnected") {
  const status = document.getElementById("status");
  const statusText = status.querySelector(".status-text");

  status.classList.remove("connected", "error");
  if (state === "connected") {
    status.classList.add("connected");
  } else if (state === "error") {
    status.classList.add("error");
  }

  statusText.textContent = text;
}

function showError(message) {
  // Handle Error objects from RPC client
  if (message instanceof Error) {
    message = message.message;
  }
  updateHeaderStatus(message, "error");
}

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
  } catch (err) {
    // Show error in status box
    showError(err);
    console.error(`[WebTap] ${buttonId} failed:`, err);
  } finally {
    btn.disabled = wasDisabled;
    globalOperationInProgress = false;
  }
}

function bindAction(id, method, params = {}) {
  document.getElementById(id).onclick = async () => {
    await withButtonLock(id, async () => {
      await client.call(method, params);
    });
  };
}

let webtapAvailable = false;

client.on("state", (state, previousState) => {
  updateConnectionStatus(state);
  updateInterceptUI(state);
  updateFiltersUI(state.filters);
  updateSelectionUI(state.browser);
  updateErrorBanner(state.error);
  updateEventCount(state.events.total);
  updateButtons(state.connected);
  updateConnectButton();

  const pageChanged = previousState?.page?.id !== state.page?.id;
  if (
    !previousState ||
    previousState.connected !== state.connected ||
    pageChanged
  ) {
    loadPages();
  }

  if (state.connected && activeTab === "network") {
    fetchNetwork();
  }
});

client.on("error", () => {
  webtapAvailable = false;

  updateHeaderStatus("Server offline", "error");

  document.getElementById("pageList").innerHTML =
    "<option disabled>Server not running</option>";

  setTimeout(() => {
    updateHeaderStatus("Reconnecting...", "error");
    client.connect();
    setTimeout(() => {
      webtapAvailable = true;
      loadPages();
    }, 1000);
  }, 2000);
});

window.addEventListener("beforeunload", () => {
  client.disconnect();
});

function updateConnectionStatus(state) {
  if (state.connected && state.page) {
    updateHeaderStatus(`Connected (${state.events.total})`, "connected");
  } else if (!state.connected) {
    updateHeaderStatus("Disconnected", "disconnected");
  }
}

function updateEventCount(count) {
  const status = document.getElementById("status");
  if (status.classList.contains("connected")) {
    const statusText = status.querySelector(".status-text");
    statusText.textContent = `Connected (${count})`;
  }
}

function updateButtons(connected) {
  document.getElementById("connectToggle").disabled = false;
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

function updateInterceptUI(state) {
  let mode = "disabled";
  if (state.fetch.enabled) {
    mode = state.fetch.response_stage ? "response" : "request";
  }

  interceptDropdown.setActive(mode);

  const labels = { disabled: "Off", request: "Req", response: "Req+Res" };
  const paused = state.fetch.paused_count || 0;
  const pausedText = paused > 0 ? ` (${paused})` : "";
  interceptDropdown.setText(`Intercept: ${labels[mode]}${pausedText}`);
  interceptDropdown.toggle.classList.toggle("active", state.fetch.enabled);
}

function updateFiltersUI(filters) {
  const filterList = document.getElementById("filterList");
  const filterStats = document.getElementById("filterStats");

  const enabled = new Set(filters.enabled || []);
  const all = [...enabled, ...(filters.disabled || [])].sort();

  filterStats.textContent = `${enabled.size}/${all.length}`;
  ui.empty(filterList);

  all.forEach((name) => {
    const isEnabled = enabled.has(name);
    const checkbox = ui.el("input", {
      attrs: { type: "checkbox", "data-filter": name },
    });
    checkbox.checked = isEnabled;
    checkbox.onchange = () => toggleFilter(name, checkbox);

    const label = ui.el("label", { children: [checkbox] });
    label.appendChild(document.createTextNode(name));
    filterList.appendChild(label);
  });
}

function updateSelectionUI(browser) {
  const selectionButton = document.getElementById("startSelection");

  if (browser.inspect_active) {
    selectionButton.textContent = "Stop Selecting";
    selectionButton.classList.add("active-selection");
  } else {
    selectionButton.textContent = "Select Elements";
    selectionButton.classList.remove("active-selection");
  }

  selectionList.update(browser.selections || {});
}

async function loadPages() {
  if (!webtapAvailable) {
    document.getElementById("pageList").innerHTML =
      "<option disabled>Select a page</option>";
    return;
  }

  try {
    const info = await client.call("pages");
    const pages = info.pages || [];
    const select = document.getElementById("pageList");
    select.innerHTML = "";

    if (pages.length === 0) {
      select.innerHTML = "<option disabled>Empty: No pages available</option>";
    } else {
      const currentPageId = client.state.page ? client.state.page.id : null;

      const selectWidth = select.clientWidth || 200;
      const charWidth = 7;
      const reservedChars = 4;
      const maxChars = Math.floor(selectWidth / charWidth) - reservedChars;

      pages.forEach((page, index) => {
        const option = document.createElement("option");
        option.value = page.id;

        const url = page.url || page.title || "Untitled";
        const shortUrl = url.replace(/^https?:\/\//, "");
        const displayUrl = truncateMiddle(shortUrl, maxChars);

        if (page.id === currentPageId) {
          option.className = "connected";
          option.selected = true;
        }

        option.textContent = `${index}: ${displayUrl}`;
        select.appendChild(option);
      });
    }
  } catch (err) {
    console.error("[WebTap] Failed to load pages:", err);
    document.getElementById("pageList").innerHTML =
      "<option disabled>Unable to load pages</option>";
  }
}

const reloadPagesBtn = document.getElementById("reloadPages");
reloadPagesBtn.textContent = icons.refresh;
reloadPagesBtn.onclick = async () => {
  await withButtonLock("reloadPages", loadPages);
};

bindAction("clear", "clear", { events: true });

// Smart connect button - handles connect, disconnect, and page switching
document.getElementById("connectToggle").onclick = async () => {
  await withButtonLock("connectToggle", async () => {
    const selectedPageId = document.getElementById("pageList").value;

    if (!selectedPageId) {
      showError("Please select a page");
      return;
    }

    const currentPageId = client.state.page?.id;
    const isConnectedToSelected =
      client.state.connected && currentPageId === selectedPageId;
    const isConnectedToDifferent =
      client.state.connected && currentPageId !== selectedPageId;

    if (isConnectedToSelected) {
      // Disconnect from current page
      await client.call("disconnect");
    } else if (isConnectedToDifferent) {
      // Switching pages - confirm first
      if (confirm("Disconnect from current page and connect to new one?")) {
        await client.call("connect", { page_id: selectedPageId });
      }
    } else {
      // Not connected - just connect
      await client.call("connect", { page_id: selectedPageId });
    }
  });
};

function updateConnectButton() {
  const btn = document.getElementById("connectToggle");
  const selectedPageId = document.getElementById("pageList").value;
  const currentPageId = client.state.page?.id;
  const isConnectedToSelected =
    client.state.connected && currentPageId === selectedPageId;

  btn.textContent = isConnectedToSelected ? "Disconnect" : "Connect";
  btn.classList.toggle("connected", isConnectedToSelected);
}

document.getElementById("pageList").onchange = updateConnectButton;

const interceptDropdown = new Dropdown("#interceptDropdown", {
  onSelect: async (mode) => {
    if (!client.state.connected) {
      showError("Connect to a page first");
      return;
    }

    try {
      if (mode === "disabled") {
        await client.call("fetch.disable");
      } else {
        await client.call("fetch.enable", {
          request: true,
          response: mode === "response",
        });
      }
    } catch (err) {
      showError(err);
    }
  },
});

async function toggleFilter(name, checkbox) {
  checkbox.disabled = true;

  try {
    const isEnabled = client.state.filters.enabled.includes(name);
    const method = isEnabled ? "filters.disable" : "filters.enable";
    await client.call(method, { name });
  } catch (err) {
    showError(err);
    // Revert checkbox on error
    const isEnabled = client.state.filters.enabled.includes(name);
    checkbox.checked = isEnabled;
  } finally {
    checkbox.disabled = false;
  }
}

document.getElementById("enableAllFilters").onclick = async (e) => {
  e.stopPropagation();
  await withButtonLock("enableAllFilters", () =>
    client.call("filters.enableAll"),
  );
};

document.getElementById("disableAllFilters").onclick = async (e) => {
  e.stopPropagation();
  await withButtonLock("disableAllFilters", () =>
    client.call("filters.disableAll"),
  );
};

document.getElementById("startSelection").onclick = async () => {
  await withButtonLock("startSelection", async () => {
    if (!client.state.connected) {
      showError("Error: Not connected to a page");
      return;
    }

    const method = client.state.browser.inspect_active
      ? "browser.stopInspect"
      : "browser.startInspect";

    await client.call(method);
  });
};

bindAction("clearSelections", "browser.clear");

bindAction("dismissError", "errors.dismiss");

let selectedRequestId = null;

async function fetchNetwork() {
  const container = document.getElementById("networkTable");
  const countEl = document.getElementById("networkCount");

  if (!client.state.connected) {
    ui.empty(container, "Connect to a page to see requests");
    countEl.textContent = "0 requests";
    return;
  }

  try {
    const result = await client.call("network", { limit: 50, order: "desc" });
    const requests = (result.requests || []).reverse();
    updateNetworkTable(requests);
    container.scrollTop = container.scrollHeight;
  } catch (err) {
    showError(err);
  }
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
    const isPaused = req.state === "paused";
    const isError = !isPaused && req.status >= 400;

    const statusText = isPaused
      ? `${icons.pause} ${req.pause_stage === "Response" ? "Res" : "Req"}`
      : String(req.status || "-");
    const statusClass = isPaused ? "paused" : isError ? "error" : "ok";

    const row = ui.row(
      "network-row" + (isPaused ? " paused" : isError ? " error" : ""),
      [
        ui.el("span", { class: "network-method", text: req.method || "GET" }),
        ui.el("span", {
          class: "network-status " + statusClass,
          text: statusText,
        }),
        ui.el("span", {
          class: "network-url",
          text: req.url || "",
          title: req.url || "",
        }),
      ],
    );
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

  if (wasHidden) {
    ui.loading(detailsEl);
  }

  try {
    const result = await client.call("request", { id });
    const entry = result.entry;
    ui.empty(detailsEl);

    detailsEl.appendChild(
      ui.row("request-details-header flex-row", [
        ui.el("span", {
          text: `${entry.request?.method || "GET"} ${entry.response?.status || ""}`,
        }),
        ui.el("button", {
          class: "icon-btn",
          text: icons.close,
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
        ui.details(
          `Request Headers (${headerCount})`,
          JSON.stringify(entry.request.headers, null, 2),
        ),
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
  } catch (err) {
    ui.empty(detailsEl, `Error: ${err.message}`);
  }
}

chrome.tabs.onActivated.addListener(() => loadPages());
chrome.tabs.onRemoved.addListener(() => loadPages());
chrome.tabs.onCreated.addListener(() => loadPages());
chrome.tabs.onMoved.addListener(() => loadPages());
chrome.tabs.onUpdated.addListener((tabId, changeInfo) => {
  if (changeInfo.status === "complete") {
    loadPages();
  }
});

document.getElementById("themeToggle").onclick = toggleTheme;
initTabs();

client.connect();
setTimeout(() => {
  webtapAvailable = true;
  loadPages();
}, 500);

let lastPageListWidth = 0;
new ResizeObserver((entries) => {
  const width = entries[0]?.contentRect.width || 0;
  if (width > 0 && Math.abs(width - lastPageListWidth) > 10) {
    lastPageListWidth = width;
    if (webtapAvailable) loadPages();
  }
}).observe(document.getElementById("pageList"));
