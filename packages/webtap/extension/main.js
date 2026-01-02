/**
 * WebTap Extension - Main Entry Point
 * Wires together all controllers and handles global state/events.
 */

import { WebTapClient } from "./client.js";
import { Bind } from "./bind.js";
import { DataTable } from "./datatable.js";
import { icons, ui } from "./lib/ui.js";
import * as theme from "./controllers/theme.js";
import * as tabs from "./controllers/tabs.js";
import * as header from "./controllers/header.js";
import * as notices from "./controllers/notices.js";
import * as pages from "./controllers/pages.js";
import * as targets from "./controllers/targets.js";
import * as network from "./controllers/network.js";
import * as console_ from "./controllers/console.js";
import * as filters from "./controllers/filters.js";
import * as selections from "./controllers/selections.js";
import * as intercept from "./controllers/intercept.js";

console.log("[WebTap] Side panel loaded");

// Client created async with port discovery
let client = null;
let bindings = null;

// Global state
let webtapAvailable = false;
let globalOperationInProgress = false;
let chromeListenersAttached = false;

// Shared callbacks for controllers
const callbacks = {
  onError: header.showError,
  getWebtapAvailable: () => webtapAvailable,
  withButtonLock,
};

// Button Lock
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
    header.showError(err);
    console.error(`[WebTap] ${buttonId} failed:`, err);
  } finally {
    btn.disabled = wasDisabled;
    globalOperationInProgress = false;
  }
}

function bindAction(id, method, params = {}) {
  document.getElementById(id).onclick = async () => {
    if (!client) return;
    await withButtonLock(id, async () => {
      await client.call(method, params);
    });
  };
}

// Setup event handlers on client
function setupEventHandlers() {
  // State Listener - render from SSE state (DataTable handles efficient diffing)
  client.on("state", (state, previousState) => {
    const becameAvailable = !webtapAvailable;
    if (becameAvailable) {
      webtapAvailable = true;
    }

    // Update all controllers (all cheap - DataTable diffs internally)
    header.updateConnection(state);
    header.updateError(state.errors);
    header.updateEventCount(state.events.total);
    intercept.update(state);
    targets.update(state);
    selections.update(state.browser);
    filters.update(state.filters);
    pages.updateButton();
    notices.render(state.notices, state.clients);

    // RPC calls - collect and fire in parallel (no await, fire-and-forget)
    const rpcCalls = [];

    // Pages list reload on connection changes
    if (becameAvailable || state.targets_hash !== previousState?.targets_hash) {
      rpcCalls.push(pages.load());
    }

    // Network/Console RPC only when tab active AND event count changed (expensive - fetches from DuckDB)
    if (state.connected && tabs.getActive() === "network"
        && state.events?.total !== previousState?.events?.total) {
      rpcCalls.push(network.fetch());
    }
    if (state.connected && tabs.getActive() === "console"
        && state.events?.total !== previousState?.events?.total) {
      rpcCalls.push(console_.fetch());
    }

    // Fire all RPC calls in parallel
    if (rpcCalls.length > 0) {
      Promise.all(rpcCalls).catch(() => {}); // Errors handled in individual calls
    }
  });

  client.on("error", () => {
    webtapAvailable = false;
    header.updateStatus("Server offline", "error");
    pages.clear();

    setTimeout(() => {
      header.updateStatus("Reconnecting...", "error");
      discoverAndConnect();
    }, 2000);
  });
}

// Setup UI bindings that depend on client
function setupUIBindings() {
  bindings = Bind.connect(client);

  // Button Wiring
  const reloadPagesBtn = document.getElementById("reloadPages");
  reloadPagesBtn.textContent = icons.refresh;
  reloadPagesBtn.onclick = async () => {
    await withButtonLock("reloadPages", pages.load);
  };

  bindAction("clear", "clear", { events: true });
  bindAction("clearSelections", "browser.clear");
  bindAction("dismissError", "errors.dismiss");

  document.getElementById("enableAllFilters").onclick = async (e) => {
    e.stopPropagation();
    await filters.enableAll();
  };

  document.getElementById("disableAllFilters").onclick = async (e) => {
    e.stopPropagation();
    await filters.disableAll();
  };

  document.getElementById("themeToggle").onclick = theme.toggle;

  // Chrome Tab Listeners (only attach once to prevent accumulation)
  if (!chromeListenersAttached) {
    chrome.tabs.onActivated.addListener(() => pages.load());
    chrome.tabs.onRemoved.addListener(() => pages.load());
    chrome.tabs.onCreated.addListener(() => pages.load());
    chrome.tabs.onMoved.addListener(() => pages.load());
    chrome.tabs.onUpdated.addListener((tabId, changeInfo) => {
      if (changeInfo.status === "complete") pages.load();
    });
    chromeListenersAttached = true;
  }
}

window.addEventListener("beforeunload", () => {
  if (client) client.disconnect();
});

// Port discovery and connection
async function discoverAndConnect() {
  header.updateStatus("Discovering daemon...", "disconnected");

  const discovered = await WebTapClient.create();

  if (!discovered) {
    header.updateStatus("Daemon not found", "error");
    // Retry in 5 seconds
    setTimeout(discoverAndConnect, 5000);
    return;
  }

  // First time setup
  if (!client) {
    client = discovered;

    // Initialize controllers with client
    pages.init(client, DataTable, null, callbacks);
    targets.init(client, DataTable, null, callbacks);
    network.init(client, DataTable, null, callbacks);
    console_.init(client, DataTable, null, callbacks);
    filters.init(client, DataTable, callbacks);
    selections.init(client, DataTable, callbacks);
    intercept.init(client, callbacks);

    setupEventHandlers();
    setupUIBindings();
  } else {
    // Reconnection - update baseUrl
    client.baseUrl = discovered.baseUrl;
  }

  client.connect();
}

// Initialize
theme.init();
tabs.init({
  onNetworkTabActive: () => {
    if (client && client.state.connected) {
      network.fetch();
    }
  },
  onConsoleTabActive: () => {
    if (client && client.state.connected) {
      console_.fetch();
    }
  },
});
discoverAndConnect();
