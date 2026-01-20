/**
 * Targets Controller
 * Handles the Connected Targets section with tracking and inspection.
 */

import { TablePreset, RowClass, actionButton } from "../lib/table/index.js";
import { withTableLoading } from "../lib/utils.js";

let client = null;
let targetsTable = null;
let DataTable = null;
let onError = null;

export function init(c, DT, fmt, callbacks = {}) {
  client = c;
  DataTable = DT;
  onError = callbacks.onError || console.error;

  targetsTable = new DataTable("#targetsList", {
    ...TablePreset.compactList,
    columns: [
      { key: "target", monospace: true },
      { key: "display", truncateMiddle: true },
      {
        key: "devtools",
        width: "auto",
        formatter: actionButton({
          label: "DevTools",
          className: "inspect-btn",
          disabled: (row) => !row.devtools_url,
          onClick: (row) => openDevTools(row),
        }),
      },
      {
        key: "inspect",
        width: "auto",
        formatter: actionButton({
          label: (row) => (row.inspecting ? "Stop" : "Inspect"),
          className: (row) => (row.inspecting ? "inspect-btn inspecting" : "inspect-btn"),
          onClick: (row) => (row.inspecting ? stopInspect() : startInspect(row.target)),
        }),
      },
    ],
    getKey: (row) => row.target,
    getRowClass: (row) => (row.active ? RowClass.ACTIVE : ""),
    onRowDoubleClick: (row) => toggleFilter(row, !row.active),
    emptyText: "No targets",
  });
}

function openDevTools(row) {
  if (!row.devtools_url) return;
  let url = row.devtools_url;
  if (url.startsWith("/")) {
    url = `devtools://devtools${url}`;
  } else if (url.includes("chrome-devtools-frontend.appspot.com")) {
    url = url.replace(
      /https:\/\/chrome-devtools-frontend\.appspot\.com\/serve_rev\/@[^/]+/,
      "devtools://devtools/bundled"
    );
  }
  chrome.tabs.create({ url });
}

async function startInspect(target) {
  try {
    await client.call("browser.startInspect", { target });
  } catch (err) {
    onError(err);
  }
}

async function stopInspect() {
  try {
    await client.call("browser.stopInspect");
  } catch (err) {
    onError(err);
  }
}

export function update(state) {
  const targetsSection = document.getElementById("targetsSection");
  const targetsCount = document.getElementById("targetsCount");
  const connections = state.connections || [];

  if (connections.length === 0) {
    targetsSection.classList.add("hidden");
    return;
  }

  targetsSection.classList.remove("hidden");
  targetsCount.textContent = connections.length;

  const trackedTargets = new Set(state.tracked_targets || []);
  const inspectingTarget = state.browser?.inspect_active ? state.browser?.inspecting : null;

  const data = connections.map((conn) => ({
    target: conn.target,
    display: conn.title || conn.url || "Untitled",
    active: trackedTargets.size === 0 || trackedTargets.has(conn.target),
    inspecting: conn.target === inspectingTarget,
    devtools_url: conn.devtools_url,
  }));

  if (targetsTable) targetsTable.update(data);
}

async function toggleFilter(row, checked) {
  await withTableLoading(targetsTable, "Updating...", async () => {
    const connections = client.state.connections || [];
    const connectedTargets = new Set(connections.map((c) => c.target));
    const trackedTargets = new Set(client.state.tracked_targets || []);

    if (trackedTargets.size === 0) {
      // Starting from "all active" state - unchecking one means all others become tracked
      if (!checked) {
        const others = [...connectedTargets].filter((t) => t !== row.target);
        await client.call("targets.set", { targets: others });
      }
    } else {
      if (checked) {
        trackedTargets.add(row.target);
      } else {
        trackedTargets.delete(row.target);
      }

      if (trackedTargets.size === 0 || trackedTargets.size === connectedTargets.size) {
        await client.call("targets.clear");
      } else {
        await client.call("targets.set", { targets: Array.from(trackedTargets) });
      }
    }
  }).catch(onError);
}
