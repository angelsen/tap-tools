/**
 * Network Controller
 * Handles the Network Requests table and request details panel.
 */

import { ui, icons } from "../lib/ui.js";

let client = null;
let networkTable = null;
let DataTable = null;

let onError = null;

// Local state
export let selectedRequestId = null;

// Network-specific status formatter (domain logic belongs here, not in DataTable)
function formatStatus(value, row) {
  if (row.state === "paused") {
    const badge = document.createElement("span");
    badge.className = "status-badge status-badge--warning";
    badge.textContent = row.pause_stage === "Response" ? "Res" : "Req";
    return badge;
  }
  if (!value) return "-";
  const type = value >= 400 ? "error" : value >= 300 ? "warning" : "success";
  const badge = document.createElement("span");
  badge.className = `status-badge status-badge--${type}`;
  badge.textContent = value;
  return badge;
}

export function init(c, DT, fmt, callbacks = {}) {
  client = c;
  DataTable = DT;
  onError = callbacks.onError || console.error;

  networkTable = new DataTable("#networkTable", {
    columns: [
      { key: "method", header: "Method", width: "55px" },
      { key: "status", header: "Status", width: "50px", formatter: formatStatus },
      { key: "url", header: "URL", truncate: true },
    ],
    selectable: true,
    onRowClick: (row) => showDetails(row.id, row.target),
    getKey: (row) => row.id,
    emptyText: "No requests captured",
    autoScroll: true,
  });
}

export async function fetch() {
  const countEl = document.getElementById("networkCount");

  if (!client.state.connected) {
    if (networkTable) networkTable.update([]);
    if (countEl) countEl.textContent = "0 requests";
    return;
  }

  try {
    const result = await client.call("network", { limit: 50, order: "desc" });
    const requests = (result.requests || []).reverse();
    updateTable(requests);
  } catch (err) {
    onError(err);
  }
}

function updateTable(requests) {
  const countEl = document.getElementById("networkCount");
  if (countEl) countEl.textContent = `${requests.length} requests`;

  if (networkTable) networkTable.update(requests);
}

export function closeDetails() {
  selectedRequestId = null;
  document.getElementById("requestDetails").classList.add("hidden");
}

export async function showDetails(id, target) {
  const detailsEl = document.getElementById("requestDetails");

  if (selectedRequestId === id) {
    closeDetails();
    return;
  }

  const wasHidden = detailsEl.classList.contains("hidden");
  selectedRequestId = id;
  detailsEl.classList.remove("hidden");

  if (wasHidden) {
    ui.loading(detailsEl);
  }

  try {
    const result = await client.call("request", { id, target });
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
          onclick: closeDetails,
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
