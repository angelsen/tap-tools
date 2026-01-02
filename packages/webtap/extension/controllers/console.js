/**
 * Console Controller
 * Handles the Console Messages table and entry details panel.
 */

import { ui } from "../lib/ui.js";
import {
  consoleLevel,
  timestamp,
  Width,
  TablePreset,
  RowClass,
  createDetailPanel,
} from "../lib/table/index.js";

let client = null;
let consoleTable = null;
let DataTable = null;
let detailPanel = null;
let onError = null;

export function init(c, DT, fmt, callbacks = {}) {
  client = c;
  DataTable = DT;
  onError = callbacks.onError || console.error;

  consoleTable = new DataTable("#consoleTable", {
    ...TablePreset.eventLog,
    columns: [
      { key: "level", header: "Level", width: Width.LEVEL, formatter: consoleLevel },
      { key: "source", header: "Source", width: Width.SOURCE },
      { key: "message", header: "Message", truncate: true },
      { key: "timestamp", header: "Time", width: Width.TIME, formatter: timestamp },
    ],
    onRowDoubleClick: (row) => detailPanel.show(row.id, row),
    getKey: (row) => row.id,
    getRowClass: (row) => (row.level === "error" ? RowClass.ERROR : null),
    emptyText: "No console messages",
  });

  detailPanel = createDetailPanel({
    elementId: "consoleDetails",
    fetchData: (id, row) => client.call("entry", { id, fields: ["*"] }),
    renderHeader: (data) => `${data.entry.type || "log"} - ${data.entry.source || "console"}`,
    renderContent: renderConsoleDetails,
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
  detailPanel.close();
}

function renderConsoleDetails(data, el) {
  const entry = data.entry;

  // Full message
  el.appendChild(
    ui.el("div", {
      text: entry.message || "",
      class: "console-message-full",
    })
  );

  // Stack trace if present
  if (entry.stackTrace) {
    const frames = entry.stackTrace.callFrames || [];
    if (frames.length > 0) {
      const stackText = frames
        .map(
          (f) =>
            `  at ${f.functionName || "(anonymous)"} (${f.url}:${f.lineNumber}:${f.columnNumber})`
        )
        .join("\n");
      el.appendChild(ui.details(`Stack Trace (${frames.length} frames)`, stackText));
    }
  }

  // Args if present (for consoleAPICalled)
  if (entry.args && entry.args.length > 1) {
    el.appendChild(
      ui.details(`Arguments (${entry.args.length})`, JSON.stringify(entry.args, null, 2))
    );
  }
}
