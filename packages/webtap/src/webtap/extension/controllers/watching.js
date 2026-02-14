/**
 * Watching Controller
 * Shows watched targets with live state, devtools/inspect actions.
 * Rendered from SSE state - no RPC needed.
 */

import { TablePreset, RowClass, Width, actionButton } from "../lib/table/index.js";
import { shortType, stateIcon, stateIndicator } from "../lib/target-utils.js";

let client = null;
let table = null;
let onError = null;

export function init(c, DT, callbacks = {}) {
  client = c;
  onError = callbacks.onError || console.error;

  table = new DT("#watchingList", {
    ...TablePreset.compactList,
    columns: [
      { key: "type", header: "Type", width: Width.AUTO, monospace: true },
      { key: "display", header: "Name", truncateMiddle: true, titleKey: "url" },
      { key: "state", header: "", width: Width.AUTO, formatter: stateIndicator },
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
          disabled: (row) => !row.attached,
          onClick: (row) => (row.inspecting ? stopInspect() : startInspect(row.target)),
        }),
      },
    ],
    getKey: (row) => row.target,
    getRowClass: (row) => {
      if (row.auto_attached) return RowClass.CONNECTED;
      return row.attached ? RowClass.ACTIVE : "";
    },
    emptyText: "No watched targets",
  });
}

export function update(state) {
  const section = document.getElementById("watchingSection");
  const countEl = document.getElementById("watchingCount");

  const watchedTargets = new Set(state.watched_targets || []);
  const watchedUrls = new Set(state.watched_urls || []);
  const connections = state.connections || [];
  const inspectingTarget = state.browser?.inspect_active ? state.browser?.inspecting : null;

  const watched = connections.filter(
    (c) => watchedTargets.has(c.target) || watchedUrls.has(c.url) || c.auto_attached
  );

  if (watched.length === 0) {
    section.classList.add("hidden");
    return;
  }

  section.classList.remove("hidden");
  countEl.textContent = watched.length;

  const data = watched.map((c) => ({
    target: c.target,
    type: shortType(c.type || "page"),
    display: c.title || c.url || c.target,
    url: c.url || "",
    state: stateIcon(c.state),
    attached: c.state === "attached",
    auto_attached: !!c.auto_attached,
    devtools_url: c.devtools_url,
    inspecting: c.target === inspectingTarget,
  }));

  if (table) table.update(data);
}

export async function unwatchAll() {
  try {
    await client.call("unwatch");
  } catch (err) {
    onError(err);
  }
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
