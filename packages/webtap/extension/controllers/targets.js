/**
 * Targets Controller
 * Handles the Connected Targets section with tracking and inspection.
 */


let client = null;
let targetsTable = null;
let DataTable = null;
let formatters = null;

let onError = null;

export function init(c, DT, fmt, callbacks = {}) {
  client = c;
  DataTable = DT;
  formatters = fmt;
  onError = callbacks.onError || console.error;

  targetsTable = new DataTable("#targetsList", {
    columns: [
      { key: "target", width: "auto", monospace: true },
      { key: "display", truncateMiddle: true },
      {
        key: "devtools",
        width: "auto",
        formatter: (val, row) => devToolsButton(row),
      },
      {
        key: "inspect",
        width: "auto",
        formatter: (val, row) => inspectButton(row),
      },
    ],
    getKey: (row) => row.target,
    getRowClass: (row) => row.active ? 'data-table-row--tracked' : '',
    onRowDoubleClick: (row) => toggleFilter(row, !row.active),
    emptyText: "No targets",
    compact: true,
  });
}

function devToolsButton(row) {
  const btn = document.createElement("button");
  btn.className = "inspect-btn";
  btn.textContent = "DevTools";
  btn.disabled = !row.devtools_url;
  btn.onclick = (e) => {
    e.stopPropagation();
    if (!row.devtools_url) return;
    // Chrome's devtoolsFrontendUrl is relative, make it absolute
    const url = row.devtools_url.startsWith("/")
      ? `devtools://devtools${row.devtools_url}`
      : row.devtools_url;
    chrome.tabs.create({ url });
  };
  return btn;
}

function inspectButton(row) {
  const btn = document.createElement("button");
  btn.className = row.inspecting ? "inspect-btn inspecting" : "inspect-btn";
  btn.textContent = row.inspecting ? "Stop" : "Inspect";
  btn.onclick = (e) => {
    e.stopPropagation();
    if (row.inspecting) {
      stopInspect();
    } else {
      startInspect(row.target);
    }
  };
  return btn;
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
  try {
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
  } catch (err) {
    onError(err);
  }
}
