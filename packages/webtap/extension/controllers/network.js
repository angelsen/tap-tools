/**
 * Network Controller
 * Handles the Network Requests table and request details panel.
 */

import { ui } from "../lib/ui.js";
import {
  httpStatus,
  Width,
  TablePreset,
  createDetailPanel,
} from "../lib/table/index.js";

let client = null;
let networkTable = null;
let DataTable = null;
let detailPanel = null;
let onError = null;

export function init(c, DT, fmt, callbacks = {}) {
  client = c;
  DataTable = DT;
  onError = callbacks.onError || console.error;

  networkTable = new DataTable("#networkTable", {
    ...TablePreset.eventLog,
    columns: [
      { key: "method", header: "Method", width: Width.METHOD },
      { key: "status", header: "Status", width: Width.STATUS, formatter: httpStatus },
      { key: "url", header: "URL", truncate: true },
    ],
    onRowDoubleClick: (row) => detailPanel.show(row.id, row),
    getKey: (row) => row.id,
    emptyText: "No requests captured",
  });

  detailPanel = createDetailPanel({
    elementId: "requestDetails",
    fetchData: (id, row) => client.call("request", { id, target: row.target }),
    renderHeader: (data) =>
      `${data.entry.request?.method || "GET"} ${data.entry.response?.status || ""}`,
    renderContent: renderRequestDetails,
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
  detailPanel.close();
}

export function getSelectedRequestId() {
  return detailPanel?.getSelectedId();
}

function renderRequestDetails(data, el) {
  const entry = data.entry;

  el.appendChild(
    ui.el("div", {
      text: entry.request?.url || "",
      class: "url-display",
    })
  );

  if (entry.response?.content?.mimeType) {
    el.appendChild(
      ui.el("div", {
        text: `Type: ${entry.response.content.mimeType}`,
        class: "text-muted",
      })
    );
  }

  if (entry.request?.headers) {
    const headerCount = Object.keys(entry.request.headers).length;
    el.appendChild(
      ui.details(
        `Request Headers (${headerCount})`,
        JSON.stringify(entry.request.headers, null, 2)
      )
    );
  }

  if (entry.response?.headers) {
    const headerCount = Object.keys(entry.response.headers).length;
    el.appendChild(
      ui.details(
        `Response Headers (${headerCount})`,
        JSON.stringify(entry.response.headers, null, 2)
      )
    );
  }
}
