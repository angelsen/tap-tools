/**
 * Selections Controller
 * Handles element selection mode and the selections list.
 */

import { TablePreset, Width } from "../lib/table/index.js";

let client = null;
let selectionTable = null;
let DataTable = null;

let onError = null;

export function init(c, DT, callbacks = {}) {
  client = c;
  DataTable = DT;
  onError = callbacks.onError || console.error;

  selectionTable = new DataTable("#selectionList", {
    ...TablePreset.compactList,
    columns: [
      {
        key: "badge",
        width: Width.BADGE,
        formatter: (val) => {
          const span = document.createElement("span");
          span.className = "selection-badge";
          span.textContent = val;
          return span;
        },
      },
      { key: "preview", truncate: true },
    ],
    getKey: (row) => row.id,
    emptyText: "No elements selected",
  });
}

export function update(browser) {
  const selections = browser.selections || {};
  const data = Object.entries(selections).map(([id, sel]) => {
    const preview = sel.preview || {};
    const previewText = `<${preview.tag || "?"}>${preview.id ? " #" + preview.id : ""}${
      preview.classes?.length ? " ." + preview.classes.join(".") : ""
    }`;
    return { id, badge: `#${id}`, preview: previewText };
  });

  if (selectionTable) selectionTable.update(data);
}
