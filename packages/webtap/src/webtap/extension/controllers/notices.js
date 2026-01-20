/**
 * Notices Controller
 * Renders notice banners with dismiss functionality
 */
import { icons, ui } from "../lib/ui.js";

const TYPE_CLASSES = {
  extension_installed: "notice--info",
  extension_updated: "notice--warning",
  extension_manifest_changed: "notice--warning",
  client_stale: "notice--stale",
};

export function render(notices, clients) {
  const container = document.getElementById("noticesBanner");
  container.innerHTML = "";

  const allNotices = [...(notices || [])];

  if (clients) {
    const staleClients = Object.entries(clients)
      .filter(([_, c]) => c.is_stale)
      .map(([id, c]) => ({
        type: "client_stale",
        message: `${c.client_type || "Client"} (${c.version}) in ${c.context || "unknown"} is outdated`,
        clear_on: null,
      }));
    allNotices.push(...staleClients);
  }

  if (allNotices.length === 0) {
    container.classList.add("hidden");
    return;
  }

  container.classList.remove("hidden");

  for (const notice of allNotices) {
    const typeClass = TYPE_CLASSES[notice.type] || "";
    const noticeEl = ui.el("div", { class: `notice ${typeClass}` });

    const messageEl = ui.el("span", {
      class: "notice-message",
      text: notice.message,
    });
    noticeEl.appendChild(messageEl);

    if (!notice.clear_on) {
      const dismissBtn = ui.el("button", {
        class: "notice-dismiss",
        text: icons.close,
        title: "Dismiss",
        onclick: () => {
          noticeEl.remove();
          if (container.children.length === 0) {
            container.classList.add("hidden");
          }
        },
      });
      noticeEl.appendChild(dismissBtn);
    }

    container.appendChild(noticeEl);
  }
}
