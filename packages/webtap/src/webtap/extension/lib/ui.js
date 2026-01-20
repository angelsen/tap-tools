/**
 * UI Utilities for WebTap Extension
 * Pure helpers with no state dependencies.
 */

export const icons = {
  close: "✕",
  pause: "⏸",
  play: "▶",
  stop: "■",
  error: "⚠",
  success: "✓",
  pending: "○",
  loading: "◌",
  refresh: "↻",
  arrow: "→",
};

export function truncateMiddle(str, maxLen) {
  if (!str || str.length <= maxLen) return str;
  const ellipsis = "…";
  const charsToShow = maxLen - ellipsis.length;
  const frontChars = Math.ceil(charsToShow / 2);
  const backChars = Math.floor(charsToShow / 2);
  return str.slice(0, frontChars) + ellipsis + str.slice(-backChars);
}

export const ui = {
  el(tag, opts = {}) {
    const el = document.createElement(tag);
    if (opts.class) el.className = opts.class;
    if (opts.text) el.textContent = opts.text;
    if (opts.title) el.title = opts.title;
    if (opts.onclick) el.onclick = opts.onclick;
    if (opts.attrs) {
      Object.entries(opts.attrs).forEach(([k, v]) => el.setAttribute(k, v));
    }
    if (opts.children) {
      opts.children.forEach((c) => c && el.appendChild(c));
    }
    return el;
  },

  row(className, children) {
    return this.el("div", { class: className, children });
  },

  details(summary, content) {
    const details = this.el("details");
    details.appendChild(this.el("summary", { text: summary }));
    if (typeof content === "string") {
      const pre = this.el("pre", { text: content, class: "text-muted" });
      details.appendChild(pre);
    } else {
      details.appendChild(content);
    }
    return details;
  },

  loading(el) {
    el.textContent = "Loading...";
  },

  empty(el, message = null) {
    el.innerHTML = "";
    if (message) {
      el.appendChild(this.el("div", { text: message, class: "text-muted" }));
    }
  },
};
