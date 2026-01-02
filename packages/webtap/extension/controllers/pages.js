/**
 * Pages Controller
 * Handles the Available Pages list and Connect/Disconnect functionality.
 */

import { TablePreset, RowClass, Width } from "../lib/table/index.js";
import { withTableLoading } from "../lib/utils.js";

let client = null;
let pageTable = null;
let DataTable = null;
let pageData = [];

// Exported state - can be read by main.js
export let selectedPageTarget = null;

// Callbacks set by main.js
let onError = null;
let getWebtapAvailable = null;

export function init(c, DT, fmt, callbacks = {}) {
  client = c;
  DataTable = DT;
  onError = callbacks.onError || console.error;
  getWebtapAvailable = callbacks.getWebtapAvailable || (() => true);

  pageTable = new DataTable("#pageList", {
    ...TablePreset.compactList,
    columns: [
      { key: "target", header: "Target", width: Width.AUTO, monospace: true },
      { key: "url", header: "URL", truncateMiddle: true },
    ],
    selectable: true,
    getKey: (row) => row.target,
    getRowClass: (row) => (row.connected ? RowClass.CONNECTED : ""),
    onRowClick: (row) => {
      selectedPageTarget = row.target;
      updateButton();
    },
    onRowDoubleClick: (row) => {
      selectedPageTarget = row.target;
      connectToSelected();
    },
    emptyText: "No pages available",
  });
}

export async function load() {
  if (!getWebtapAvailable()) {
    if (pageTable) pageTable.update([]);
    return;
  }

  try {
    const info = await client.call("pages");
    const pages = info.pages || [];

    pageData = pages.map((page) => ({
      target: page.target,
      url: (page.url || "").replace(/^https?:\/\//, ""),
      connected: page.connected,
    }));

    if (pageTable) pageTable.update(pageData);

    // Auto-select first connected page or first page
    const connectedPage = pageData.find((p) => p.connected);
    if (connectedPage) {
      selectedPageTarget = connectedPage.target;
      pageTable.setSelection([connectedPage.target]);
    } else if (pageData.length > 0 && !selectedPageTarget) {
      selectedPageTarget = pageData[0].target;
      pageTable.setSelection([pageData[0].target]);
    }

    updateButton();
  } catch (err) {
    console.error("[WebTap] Failed to load pages:", err);
    if (pageTable) pageTable.update([]);
  }
}

export function updateButton() {
  // No-op: Connect button removed, double-click handles connect/disconnect
}

async function connectToSelected() {
  if (!selectedPageTarget) {
    onError("Please select a page");
    return;
  }

  const row = pageData.find((p) => p.target === selectedPageTarget);
  const connectedTargets = new Set((client.state.connections || []).map((c) => c.target));
  const isConnectedToSelected = connectedTargets.has(selectedPageTarget);

  const message = isConnectedToSelected
    ? "Disconnecting..."
    : `Connecting to ${row?.url || selectedPageTarget}...`;

  await withTableLoading(pageTable, message, async () => {
    if (isConnectedToSelected) {
      await client.call("disconnect", { target: selectedPageTarget });
    } else {
      await client.call("connect", { target: selectedPageTarget });
    }
  }).catch(onError);
}

export function clear() {
  pageData = [];
  if (pageTable) pageTable.update([]);
}
