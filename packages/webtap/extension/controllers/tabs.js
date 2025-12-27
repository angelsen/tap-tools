/**
 * Tabs Controller
 * Manages tab switching with network fetch callback
 */

let activeTab = localStorage.getItem("webtap-tab") || "pages";
let onNetworkTabActive = null;
let onConsoleTabActive = null;

export function init(callbacks = {}) {
  onNetworkTabActive = callbacks.onNetworkTabActive || null;
  onConsoleTabActive = callbacks.onConsoleTabActive || null;

  const tabButtons = document.querySelectorAll(".tab-button");
  const tabContents = document.querySelectorAll(".tab-content");

  tabButtons.forEach((btn) => {
    const tab = btn.dataset.tab;
    btn.classList.toggle("active", tab === activeTab);
    btn.setAttribute("aria-selected", tab === activeTab);
  });

  tabContents.forEach((content) => {
    content.classList.toggle("active", content.dataset.tab === activeTab);
  });

  tabButtons.forEach((btn) => {
    btn.addEventListener("click", () => switchTo(btn.dataset.tab));
  });
}

export function switchTo(tabName) {
  if (tabName === activeTab) return;

  activeTab = tabName;
  localStorage.setItem("webtap-tab", tabName);

  document.querySelectorAll(".tab-button").forEach((btn) => {
    const isActive = btn.dataset.tab === tabName;
    btn.classList.toggle("active", isActive);
    btn.setAttribute("aria-selected", isActive);
  });

  document.querySelectorAll(".tab-content").forEach((content) => {
    content.classList.toggle("active", content.dataset.tab === tabName);
  });

  if (onNetworkTabActive && tabName === "network") {
    onNetworkTabActive();
  }
  if (onConsoleTabActive && tabName === "console") {
    onConsoleTabActive();
  }
}

export function getActive() {
  return activeTab;
}
