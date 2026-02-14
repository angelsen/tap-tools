/**
 * Targets Controller
 * Discovery list with filter. Double-click to watch/unwatch.
 * State shown via colored indicators (no checkboxes).
 */

import { TablePreset, RowClass, Width } from "../lib/table/index.js";
import { shortType, stateIcon, stateIndicator } from "../lib/target-utils.js";

let client = null;
let table = null;
let allTargetData = [];
let filterText = "";
let onError = null;

export function init(c, DT, callbacks = {}) {
  client = c;
  onError = callbacks.onError || console.error;

  table = new DT("#targetList", {
    ...TablePreset.compactList,
    columns: [
      { key: "type", header: "Type", width: Width.AUTO, monospace: true, titleKey: "parent" },
      { key: "display", header: "Name", truncateMiddle: true, titleKey: "url" },
      { key: "state", header: "", width: Width.AUTO, formatter: stateIndicator },
    ],
    getKey: (row) => row.target,
    getRowClass: (row) => (row.attached ? RowClass.ACTIVE : ""),
    onRowDoubleClick: (row) => toggleWatch(row),
    emptyText: "No targets",
  });
}

export async function load() {
  try {
    const result = await client.call("targets");
    allTargetData = (result.targets || []).map((t) => ({
      target: t.target,
      type: shortType(t.type),
      display: t.title || t.url || t.target,
      url: t.url || "",
      parent: t.parent || "",
      watched: t.watched,
      attached: t.attached,
      state: stateIcon(t.state),
    }));
    applyFilter();
  } catch (err) {
    console.error("[WebTap] Failed to load targets:", err);
    if (table) table.update([]);
  }
}

function getVisible() {
  if (!filterText) return allTargetData;
  return allTargetData.filter(
    (t) =>
      t.display.toLowerCase().includes(filterText) ||
      t.url.toLowerCase().includes(filterText) ||
      t.type.toLowerCase().includes(filterText)
  );
}

function applyFilter() {
  if (table) table.update(getVisible());
}

export function setFilter(text) {
  filterText = text.toLowerCase();
  applyFilter();
}

export async function watchAll() {
  const unwatched = getVisible().filter((t) => !t.watched).map((t) => t.target);
  if (unwatched.length) {
    try {
      await client.call("watch", { targets: unwatched });
    } catch (err) {
      onError(err);
    }
  }
}

async function toggleWatch(row) {
  try {
    if (row.watched) {
      await client.call("unwatch", { targets: [row.target] });
    } else {
      await client.call("watch", { targets: [row.target] });
    }
  } catch (err) {
    onError(err);
  }
}

export function clear() {
  allTargetData = [];
  if (table) table.update([]);
}
