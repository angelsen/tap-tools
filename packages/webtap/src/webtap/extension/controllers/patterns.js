/**
 * URL Patterns Controller
 * Manages watched URL patterns with add/remove.
 * Rendered from SSE state - patterns list with remove buttons.
 */

import { TablePreset, actionButton } from "../lib/table/index.js";

let client = null;
let table = null;
let onError = null;

export function init(c, DT, callbacks = {}) {
  client = c;
  onError = callbacks.onError || console.error;

  table = new DT("#patternList", {
    ...TablePreset.compactList,
    columns: [
      { key: "pattern", truncate: true, monospace: true },
      {
        key: "remove",
        width: "auto",
        formatter: actionButton({
          label: "✕",
          className: "icon-btn",
          onClick: (row) => removePattern(row.pattern),
        }),
      },
    ],
    getKey: (row) => row.pattern,
    emptyText: "",
  });
}

export function update(state) {
  const patterns = state.watched_patterns || [];
  if (table) table.update(patterns.map((p) => ({ pattern: p })));
}

async function removePattern(pattern) {
  try {
    await client.call("unwatch", { urls: [pattern] });
  } catch (err) {
    onError(err);
  }
}
