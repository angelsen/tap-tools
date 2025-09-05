// API helper - communicate with WebTap service
async function api(endpoint, method = "GET", body = null) {
  try {
    const opts = { method };
    if (body) {
      opts.headers = { "Content-Type": "application/json" };
      opts.body = JSON.stringify(body);
    }
    const resp = await fetch(`http://localhost:8765${endpoint}`, opts);
    return await resp.json();
  } catch (e) {
    return { error: e.message };
  }
}

// No local state - always query from WebTap

// Load available pages from WebTap
async function loadPages() {
  const result = await api("/pages");

  if (result.error) {
    document.getElementById("pageList").innerHTML =
      "<option disabled>WebTap not running</option>";
    return;
  }

  const pages = result.pages || [];
  const select = document.getElementById("pageList");

  select.innerHTML = "";

  if (pages.length === 0) {
    select.innerHTML = "<option disabled>No pages available</option>";
  } else {
    pages.forEach((page, index) => {
      const option = document.createElement("option");
      option.value = page.id; // Use stable page ID

      // Format display: index number + title
      const title = page.title || "Untitled";
      const shortTitle =
        title.length > 50 ? title.substring(0, 47) + "..." : title;

      let typeIndicator = "";
      if (page.type === "service_worker") {
        typeIndicator = " [sw]";
      }

      // Style connected page (server tells us which one)
      if (page.is_connected) {
        option.style.fontWeight = "bold";
        option.style.color = "#080";
        option.selected = true; // Select it
      }

      option.textContent = `${index}: ${shortTitle}${typeIndicator}`;
      select.appendChild(option);
    });
  }
}

// Connect to selected page
document.getElementById("connect").onclick = async () => {
  const select = document.getElementById("pageList");
  const selectedPageId = select.value;

  if (!selectedPageId) {
    document.getElementById("status").innerHTML =
      '<span class="error">Please select a page</span>';
    return;
  }

  const result = await api("/connect", "POST", { page_id: selectedPageId });

  if (result.error) {
    document.getElementById("status").innerHTML =
      `<span class="error">Error: ${result.error}</span>`;
  } else {
    document.getElementById("status").innerHTML =
      `<span class="connected">Connected</span>`;
    // Immediately update to show fresh state
    setTimeout(updateStatus, 100);
    setTimeout(loadPages, 100); // Refresh page list to show connected state
  }
};

// Disconnect from current page
document.getElementById("disconnect").onclick = async () => {
  const result = await api("/disconnect", "POST");
  document.getElementById("status").innerHTML = "Disconnected";
  // Update to reflect disconnected state
  setTimeout(updateStatus, 100);
};

// Refresh page list
document.getElementById("refresh").onclick = async () => {
  await loadPages();
  await updateStatus();
};

// Clear event buffer (keeps connection)
document.getElementById("clear").onclick = async () => {
  const result = await api("/clear", "POST");

  if (!result.error) {
    document.getElementById("status").innerHTML =
      '<span class="connected">Events cleared</span>';
    setTimeout(updateStatus, 1000);
  }
};

// Toggle fetch interception on/off
document.getElementById("fetchToggle").onclick = async () => {
  // Get current state from server
  const status = await api("/status");

  if (!status.connected) {
    document.getElementById("status").innerHTML =
      '<span class="error">Connect to a page first</span>';
    return;
  }

  // Toggle opposite of current server state
  const newState = !status.fetch_enabled;
  const responseStage = document.getElementById("responseStage").checked;
  const result = await api("/fetch", "POST", {
    enabled: newState,
    response_stage: responseStage,
  });

  if (!result.error) {
    const stages =
      result.stages ||
      (responseStage ? "Request and Response" : "Request only");
    document.getElementById("status").innerHTML =
      `<span class="connected">Intercept ${result.enabled ? "enabled" : "disabled"} (${stages})</span>`;
    // Update display immediately
    setTimeout(updateStatus, 100);
  } else {
    document.getElementById("status").innerHTML =
      `<span class="error">Error: ${result.error}</span>`;
  }
};

// Update fetch status display based on server state
function updateFetchStatus(
  fetchEnabled,
  pausedCount = 0,
  responseStage = false,
) {
  const statusSpan = document.getElementById("fetchStatus");
  const toggleBtn = document.getElementById("fetchToggle");
  const pausedInfo = document.getElementById("pausedInfo");
  const pausedCountSpan = document.getElementById("pausedCount");
  const responseCheckbox = document.getElementById("responseStage");

  if (fetchEnabled) {
    statusSpan.textContent = "ON";
    statusSpan.style.color = "#080";
    toggleBtn.classList.add("on");

    // Update response stage checkbox if we know the state
    if (responseStage !== undefined) {
      responseCheckbox.checked = responseStage;
    }

    // Show paused info if there are paused requests
    if (pausedCount > 0) {
      pausedInfo.style.display = "block";
      pausedCountSpan.textContent = pausedCount;
    } else {
      pausedInfo.style.display = "none";
    }
  } else {
    statusSpan.textContent = "OFF";
    statusSpan.style.color = "#888";
    toggleBtn.classList.remove("on");
    pausedInfo.style.display = "none";
  }
}

// Update filter display
async function updateFilters() {
  const result = await api("/filters/status");

  const filterList = document.getElementById("filterList");
  const filterStats = document.getElementById("filterStats");

  if (result.error || !result.filters) {
    filterList.innerHTML =
      '<span style="color: #888; font-size: 11px;">No filters loaded</span>';
    filterStats.textContent = "0 patterns";
    return;
  }

  // Build checkbox list
  filterList.innerHTML = "";
  let totalPatterns = 0;
  let enabledPatterns = 0;

  Object.keys(result.filters).forEach((category) => {
    const filter = result.filters[category];
    const isEnabled = result.enabled.includes(category);
    const patternCount =
      (filter.domains?.length || 0) + (filter.types?.length || 0);

    totalPatterns += patternCount;
    if (isEnabled) enabledPatterns += patternCount;

    const label = document.createElement("label");
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = isEnabled;
    checkbox.dataset.category = category;

    // Toggle category on change
    checkbox.onchange = async () => {
      await api(`/filters/toggle/${category}`, "POST");
      // Update display after toggle
      setTimeout(updateFilters, 100);
    };

    label.appendChild(checkbox);
    label.appendChild(document.createTextNode(category));

    const count = document.createElement("span");
    count.className = "filter-count";
    count.textContent = `(${patternCount})`;
    label.appendChild(count);

    filterList.appendChild(label);
  });

  // Update stats
  filterStats.textContent = `${enabledPatterns}/${totalPatterns} patterns active`;
}

// Enable/disable all filters
document.getElementById("enableAllFilters").onclick = async () => {
  await api("/filters/enable-all", "POST");
  setTimeout(updateFilters, 100);
};

document.getElementById("disableAllFilters").onclick = async () => {
  await api("/filters/disable-all", "POST");
  setTimeout(updateFilters, 100);
};

// Update all status from server - single source of truth
async function updateStatus() {
  const status = await api("/status");

  if (status.error) {
    // WebTap not running
    document.getElementById("status").innerHTML =
      '<span class="error">WebTap not running</span>';
    document.getElementById("connect").disabled = true;
    document.getElementById("fetchToggle").disabled = true;
    updateFetchStatus(false);
  } else {
    // WebTap is running
    document.getElementById("connect").disabled = false;
    document.getElementById("fetchToggle").disabled = !status.connected;

    if (status.connected) {
      // Connected - show event count
      document.getElementById("status").innerHTML =
        `<span class="connected">Connected</span> - Events: ${status.events}`;

      // Get fetch details if enabled
      if (status.fetch_enabled) {
        const fetchDetails = await api("/fetch/paused");
        updateFetchStatus(
          true,
          status.paused_requests || 0,
          fetchDetails.response_stage || false,
        );
      } else {
        updateFetchStatus(false);
      }
    } else {
      // Not connected
      document.getElementById("status").innerHTML = "Not connected";
      updateFetchStatus(false);
    }
  }

  // Also update filters
  await updateFilters();
}

// Initialize on load
loadPages();
updateStatus();

// Poll status every 2 seconds to stay in sync with WebTap
setInterval(updateStatus, 2000);
