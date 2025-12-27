/**
 * Console Controller
 * Handles the Console Messages table and entry details panel.
 */

import { ui, icons } from "../lib/ui.js";

let client = null;
let consoleTable = null;
let DataTable = null;
let formatters = null;

let onError = null;

// Local state
export let selectedEntryId = null;

function formatLevel(value) {
  const badge = document.createElement("span");
  const levelClass =
    {
      error: "error",
      warning: "warning",
      log: "muted",
      info: "info",
      debug: "muted",
    }[value] || "muted";

  badge.className = `status-badge status-badge--${levelClass}`;
  badge.textContent = value || "log";
  return badge;
}

function formatTime(value) {
  if (!value) return "-";
  // Timestamp is already in ms (wallTime * 1000 from backend)
  const date = new Date(value);
  return date.toLocaleTimeString("en-US", {
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export function init(c, DT, fmt, callbacks = {}) {
  client = c;
  DataTable = DT;
  formatters = fmt;
  onError = callbacks.onError || console.error;

  consoleTable = new DataTable("#consoleTable", {
    columns: [
      { key: "level", header: "Level", width: "60px", formatter: formatLevel },
      { key: "source", header: "Source", width: "70px" },
      { key: "message", header: "Message", truncate: true },
      { key: "timestamp", header: "Time", width: "65px", formatter: formatTime },
    ],
    selectable: true,
    onRowClick: (row) => showDetails(row.id),
    getKey: (row) => row.id,
    getRowClass: (row) => (row.level === "error" ? "data-table-row--error" : null),
    emptyText: "No console messages",
    autoScroll: true,
  });
}

export async function fetch() {
  const countEl = document.getElementById("consoleCount");

  if (!client.state.connected) {
    if (consoleTable) consoleTable.update([]);
    if (countEl) countEl.textContent = "0 messages";
    return;
  }

  try {
    const result = await client.call("console", { limit: 100 });
    const messages = (result.messages || []).reverse();
    updateTable(messages);
  } catch (err) {
    onError(err);
  }
}

function updateTable(messages) {
  const countEl = document.getElementById("consoleCount");
  if (countEl) countEl.textContent = `${messages.length} messages`;

  if (consoleTable) consoleTable.update(messages);
}

export function closeDetails() {
  selectedEntryId = null;
  document.getElementById("consoleDetails").classList.add("hidden");
}

export async function showDetails(id) {
  const detailsEl = document.getElementById("consoleDetails");

  if (selectedEntryId === id) {
    closeDetails();
    return;
  }

  const wasHidden = detailsEl.classList.contains("hidden");
  selectedEntryId = id;
  detailsEl.classList.remove("hidden");

  if (wasHidden) {
    ui.loading(detailsEl);
  }

  try {
    const result = await client.call("entry", { id, fields: ["*"] });
    const entry = result.entry;
    ui.empty(detailsEl);

    // Header with close button
    detailsEl.appendChild(
      ui.row("console-details-header flex-row", [
        ui.el("span", {
          text: `${entry.type || "log"} - ${entry.source || "console"}`,
        }),
        ui.el("button", {
          class: "icon-btn",
          text: icons.close,
          title: "Close",
          onclick: closeDetails,
        }),
      ]),
    );

    // Full message
    detailsEl.appendChild(
      ui.el("div", {
        text: entry.message || "",
        class: "console-message-full",
      }),
    );

    // Stack trace if present
    if (entry.stackTrace) {
      const frames = entry.stackTrace.callFrames || [];
      if (frames.length > 0) {
        const stackText = frames
          .map(
            (f) =>
              `  at ${f.functionName || "(anonymous)"} (${f.url}:${f.lineNumber}:${f.columnNumber})`,
          )
          .join("\n");
        detailsEl.appendChild(ui.details(`Stack Trace (${frames.length} frames)`, stackText));
      }
    }

    // Args if present (for consoleAPICalled)
    if (entry.args && entry.args.length > 1) {
      detailsEl.appendChild(
        ui.details(`Arguments (${entry.args.length})`, JSON.stringify(entry.args, null, 2)),
      );
    }
  } catch (err) {
    ui.empty(detailsEl, `Error: ${err.message}`);
  }
}
