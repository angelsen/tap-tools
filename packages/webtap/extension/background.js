// WebTap Background Service Worker
// Handles UI mode switching (sidepanel vs popup window)

console.log("[WebTap] Background service worker loaded");

// Default mode
const DEFAULT_MODE = "sidepanel";

// Initialize context menu on install
chrome.runtime.onInstalled.addListener(() => {
  createContextMenus();
});

// Create context menu items
function createContextMenus() {
  chrome.contextMenus.removeAll(() => {
    chrome.contextMenus.create({
      id: "open-sidepanel",
      title: "Open as Side Panel",
      contexts: ["action"],
    });

    chrome.contextMenus.create({
      id: "open-popup",
      title: "Open as Popup Window",
      contexts: ["action"],
    });

    chrome.contextMenus.create({
      id: "separator",
      type: "separator",
      contexts: ["action"],
    });

    chrome.contextMenus.create({
      id: "close-sidepanel",
      title: "Close Side Panel",
      contexts: ["action"],
    });
  });
}

// Handle context menu clicks
chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId === "open-sidepanel") {
    chrome.sidePanel.open({ windowId: tab.windowId });
  } else if (info.menuItemId === "open-popup") {
    chrome.windows.create({
      url: chrome.runtime.getURL("sidepanel.html"),
      type: "popup",
      width: 600,
      height: 900,
      focused: true,
    });
  } else if (info.menuItemId === "close-sidepanel") {
    chrome.sidePanel.setOptions({ enabled: false, tabId: tab.id });
  }
});

// Handle extension icon click (default: sidepanel)
chrome.action.onClicked.addListener(async (tab) => {
  chrome.sidePanel.open({ windowId: tab.windowId });
});
