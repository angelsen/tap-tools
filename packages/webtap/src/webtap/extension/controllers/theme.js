/**
 * Theme Controller
 * Manages theme toggle: auto → light → dark → auto
 */

export function init() {
  const saved = localStorage.getItem("webtap-theme");
  if (saved) {
    document.documentElement.dataset.theme = saved;
  }
  _updateButton();
}

export function toggle() {
  const current = document.documentElement.dataset.theme;
  const next = !current ? "light" : current === "light" ? "dark" : null;

  if (next) {
    document.documentElement.dataset.theme = next;
    localStorage.setItem("webtap-theme", next);
  } else {
    delete document.documentElement.dataset.theme;
    localStorage.removeItem("webtap-theme");
  }

  _updateButton();
}

function _updateButton() {
  const btn = document.getElementById("themeToggle");
  if (!btn) return;

  const theme = document.documentElement.dataset.theme;
  btn.textContent = theme === "light" ? "Light" : theme === "dark" ? "Dark" : "Auto";
}
