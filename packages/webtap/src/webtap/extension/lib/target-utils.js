/**
 * Shared target display helpers.
 * Used by targets.js and watching.js controllers.
 */

import { icons } from "./ui.js";

const TYPE_LABELS = {
  service_worker: "sw",
  background_page: "bg",
  page: "page",
  worker: "worker",
};

export function shortType(type) {
  return TYPE_LABELS[type] || type;
}

export function stateIcon(state) {
  if (state === "attached") return icons.attached;
  if (state === "connecting") return icons.loading;
  if (state === "suspended") return icons.suspended;
  return "";
}

export function stateIndicator(value) {
  const span = document.createElement("span");
  span.textContent = value;
  if (value === icons.attached) span.style.color = "var(--color-success)";
  if (value === icons.loading) span.style.color = "var(--color-muted)";
  if (value === icons.suspended) span.style.color = "var(--color-warning)";
  if (value === icons.detached) span.style.color = "var(--color-muted)";
  return span;
}
