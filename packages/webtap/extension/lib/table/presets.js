/**
 * Table Presets - Constants and preset configurations for DataTable
 */

/**
 * Semantic CSS class names for row states
 */
export const RowClass = {
  SELECTED: "data-table-row--selected",
  ERROR: "data-table-row--error",
  CONNECTED: "data-table-row--connected",
  ACTIVE: "data-table-row--active",
  ENABLED: "data-table-row--enabled",
};

/**
 * Column width constants
 */
export const Width = {
  BADGE: "35px",
  STATUS: "50px",
  METHOD: "55px",
  LEVEL: "60px",
  SOURCE: "70px",
  TIME: "65px",
  AUTO: "auto",
};

/**
 * Table configuration presets
 */
export const TablePreset = {
  /** Network/Console: scrolling event log with detail panel */
  eventLog: {
    selectable: true,
    autoScroll: true,
    emptyText: "No items captured",
  },

  /** Pages/Targets/Filters: compact toggle lists */
  compactList: {
    compact: true,
    emptyText: "No items",
  },
};

/**
 * Helper: conditional row class
 * @param {Function} condition - (row) => boolean
 * @param {string} className - class to apply when condition is true
 * @returns {Function} getRowClass function
 */
export const rowClassIf = (condition, className) => (row) =>
  condition(row) ? className : "";
