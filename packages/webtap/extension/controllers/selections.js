/**
 * Selections Controller
 * Handles element selection mode and the selections list.
 */

let client = null;
let selectionTable = null;
let DataTable = null;

let onError = null;

export function init(c, DT, callbacks = {}) {
  client = c;
  DataTable = DT;
  onError = callbacks.onError || console.error;

  selectionTable = new DataTable("#selectionList", {
    columns: [
      {
        key: "badge",
        width: "35px",
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
    compact: true,
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
