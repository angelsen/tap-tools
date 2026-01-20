/**
 * Detail Panel - Reusable show/hide/loading pattern for detail views
 */

import { ui, icons } from "../ui.js";

/**
 * Create a detail panel with standard show/hide/loading behavior
 * @param {Object} options
 * @param {string} options.elementId - DOM element ID for the panel
 * @param {Function} options.fetchData - (id, row) => Promise<data>
 * @param {Function} options.renderHeader - (data) => string
 * @param {Function} options.renderContent - (data, element) => void
 * @returns {{ show, close, getSelectedId }}
 */
export function createDetailPanel({ elementId, fetchData, renderHeader, renderContent }) {
  const el = document.getElementById(elementId);
  let selectedId = null;

  function close() {
    selectedId = null;
    el.classList.add("hidden");
  }

  async function show(id, row) {
    // Toggle off if same ID
    if (selectedId === id) {
      close();
      return;
    }

    const wasHidden = el.classList.contains("hidden");
    selectedId = id;
    el.classList.remove("hidden");

    if (wasHidden) {
      ui.loading(el);
    }

    try {
      const data = await fetchData(id, row);
      ui.empty(el);

      el.appendChild(
        ui.row("details-header flex-row", [
          ui.el("span", { text: renderHeader(data) }),
          ui.el("button", {
            class: "icon-btn",
            text: icons.close,
            title: "Close",
            onclick: close,
          }),
        ])
      );

      renderContent(data, el);
    } catch (err) {
      ui.empty(el, `Error: ${err.message}`);
    }
  }

  return { show, close, getSelectedId: () => selectedId };
}
