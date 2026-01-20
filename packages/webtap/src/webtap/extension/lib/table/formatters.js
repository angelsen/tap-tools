/**
 * Table Formatters - Reusable DataTable formatter functions
 */

/**
 * Factory for colored status badges
 * @param {Object} statusMap - Maps values to badge types (error, warning, success, info, muted)
 * @returns {Function} DataTable-compatible formatter
 */
export function colorBadge(statusMap) {
  return (value, row) => {
    const type = statusMap[value] || statusMap.default || "muted";
    const el = document.createElement("span");
    el.className = `status-badge status-badge--${type}`;
    el.textContent = value ?? "";
    return el;
  };
}

/**
 * Pause stage badge for intercepted requests
 */
function pauseBadge(stage) {
  const el = document.createElement("span");
  el.className = "status-badge status-badge--warning";
  el.textContent = stage === "Response" ? "Res" : "Req";
  return el;
}

/**
 * HTTP status code formatter - handles paused state and dynamic coloring
 */
export function httpStatus(value, row) {
  if (row.state === "paused") {
    return pauseBadge(row.pause_stage);
  }
  if (!value) return "-";
  const type = value >= 400 ? "error" : value >= 300 ? "warning" : "success";
  const el = document.createElement("span");
  el.className = `status-badge status-badge--${type}`;
  el.textContent = value;
  return el;
}

/**
 * Console log level badge
 */
export const consoleLevel = colorBadge({
  error: "error",
  warning: "warning",
  info: "info",
  log: "muted",
  debug: "muted",
  default: "muted",
});

/**
 * Timestamp formatter - HH:MM:SS
 */
export function timestamp(value) {
  if (!value) return "-";
  return new Date(value).toLocaleTimeString("en-US", {
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

/**
 * Action button factory
 * @param {Object} options - { label, onClick, disabled, className }
 * @returns {Function} DataTable-compatible formatter
 */
export function actionButton({ label, onClick, disabled, className }) {
  return (value, row) => {
    const btn = document.createElement("button");
    btn.className = typeof className === "function" ? className(row) : className || "action-btn";
    btn.textContent = typeof label === "function" ? label(row) : label;
    btn.disabled = typeof disabled === "function" ? disabled(row) : !!disabled;
    btn.onclick = (e) => {
      e.stopPropagation();
      onClick(row, e);
    };
    return btn;
  };
}
