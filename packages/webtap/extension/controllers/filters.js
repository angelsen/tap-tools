/**
 * Filters Controller
 * Handles the network filters list and All/None buttons.
 */

let client = null;
let filterTable = null;
let DataTable = null;

let onError = null;
let withButtonLock = null;

export function init(c, DT, callbacks = {}) {
  client = c;
  DataTable = DT;
  onError = callbacks.onError || console.error;
  withButtonLock = callbacks.withButtonLock || ((id, fn) => fn());

  filterTable = new DataTable("#filterList", {
    columns: [{ key: "name", truncate: true }],
    getKey: (row) => row.name,
    getRowClass: (row) => (row.enabled ? "data-table-row--tracked" : ""),
    onRowDoubleClick: (row) => toggle(row.name, !row.enabled),
    emptyText: "No filters defined",
    compact: true,
  });
}

export function update(filters) {
  const filterStats = document.getElementById("filterStats");

  const enabled = new Set(filters.enabled || []);
  const all = [...enabled, ...(filters.disabled || [])].sort();

  filterStats.textContent = `${enabled.size}/${all.length}`;

  const data = all.map((name) => ({
    name,
    enabled: enabled.has(name),
  }));

  if (filterTable) filterTable.update(data);
}

async function toggle(name, checked) {
  try {
    const method = checked ? "filters.enable" : "filters.disable";
    await client.call(method, { name });
  } catch (err) {
    onError(err);
  }
}

export async function enableAll() {
  await withButtonLock("enableAllFilters", () => client.call("filters.enableAll"));
}

export async function disableAll() {
  await withButtonLock("disableAllFilters", () => client.call("filters.disableAll"));
}
