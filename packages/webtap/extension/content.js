// WebTap Badge Renderer - Displays element selection badges only
// All element selection logic moved to CDP backend

console.log("[WebTap] Badge renderer loaded");

// Track rendered badges - Map<selectionId, badgeElement>
const renderedBadges = new Map();

// Listen for badge updates from side panel
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  console.log("[WebTap] Received message:", msg.action);

  if (msg.action === "ping") {
    // Health check - respond immediately
    sendResponse({ ready: true });
  } else if (msg.action === "updateBadges") {
    updateBadges(msg.selections);
    sendResponse({ success: true });
  } else if (msg.action === "clearBadges") {
    clearAllBadges();
    sendResponse({ success: true });
  }

  return true; // Keep channel open for async response
});

/**
 * Update badges incrementally - add new, remove deleted
 */
function updateBadges(selections) {
  const selectionIds = new Set(Object.keys(selections));

  // Add new badges
  Object.entries(selections).forEach(([id, data]) => {
    if (!renderedBadges.has(id) && data.badge) {
      const badge = createBadge(id, data.badge.x, data.badge.y);
      renderedBadges.set(id, badge);
    }
  });

  // Remove badges for deleted selections
  renderedBadges.forEach((badge, id) => {
    if (!selectionIds.has(id)) {
      badge.remove();
      renderedBadges.delete(id);
    }
  });

  console.log(`[WebTap] Badges updated: ${renderedBadges.size} active`);
}

/**
 * Create a badge element at specified position
 */
function createBadge(id, x, y) {
  const badge = document.createElement("div");
  badge.className = "webtap-badge";
  badge.dataset.selectionId = id;
  badge.textContent = `#${id}`;

  // Position with scroll offset
  badge.style.cssText = `
    position: absolute;
    top: ${y + window.scrollY}px;
    left: ${x}px;
    background: #4CAF50;
    color: white;
    padding: 4px 8px;
    border-radius: 4px;
    font: bold 12px monospace;
    z-index: 2147483647;
    pointer-events: none;
    box-shadow: 0 2px 4px rgba(0,0,0,0.3);
    transition: opacity 0.2s;
  `;

  document.body.appendChild(badge);
  return badge;
}

/**
 * Clear all badges from page
 */
function clearAllBadges() {
  renderedBadges.forEach((badge) => {
    if (badge.parentNode) {
      badge.parentNode.removeChild(badge);
    }
  });
  renderedBadges.clear();
  console.log("[WebTap] All badges cleared");
}

// Clear badges on navigation
window.addEventListener("beforeunload", () => {
  clearAllBadges();
});
