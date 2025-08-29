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

// Don't track state locally - always query from WebTap
let pages = [];

// Load available pages from WebTap
async function loadPages() {
  const result = await api("/pages");
  
  if (result.error) {
    document.getElementById("pageList").innerHTML = 
      '<option disabled>WebTap not running</option>';
    return;
  }
  
  pages = result.pages || [];
  const select = document.getElementById("pageList");
  
  // Get current status to see which page is connected
  const status = await api("/status");
  let connectedIndex = -1;
  
  // Find connected page index
  if (status.connected && status.url) {
    pages.forEach((page, index) => {
      if (page.url === status.url) {
        connectedIndex = index;
      }
    });
  }
  
  select.innerHTML = '';
  
  if (pages.length === 0) {
    select.innerHTML = '<option disabled>No pages available</option>';
  } else {
    pages.forEach((page, index) => {
      const option = document.createElement('option');
      option.value = index;
      
      // Format display: index number + title
      // Service workers get [sw] indicator since title doesn't make it clear
      const title = page.title || 'Untitled';
      const shortTitle = title.length > 50 ? title.substring(0, 47) + '...' : title;
      
      let typeIndicator = '';
      if (page.type === 'service_worker') {
        typeIndicator = ' [sw]';
      }
      
      // Style connected page
      if (index === connectedIndex) {
        option.style.fontWeight = 'bold';
        option.style.color = '#080';
      }
      
      option.textContent = `${index}: ${shortTitle}${typeIndicator}`;
      select.appendChild(option);
    });
    
    // Select the connected page if any
    if (connectedIndex >= 0) {
      select.value = connectedIndex;
    }
  }
}

// Connect to selected page
document.getElementById("connect").onclick = async () => {
  const select = document.getElementById("pageList");
  const selectedIndex = select.value;
  
  if (selectedIndex === '' || selectedIndex === null) {
    document.getElementById("status").innerHTML = 
      '<span class="error">Please select a page</span>';
    return;
  }
  
  const result = await api("/connect", "POST", { page_index: parseInt(selectedIndex) });
  
  if (result.error) {
    document.getElementById("status").innerHTML = 
      `<span class="error">Error: ${result.error}</span>`;
  } else {
    document.getElementById("status").innerHTML = 
      `<span class="connected">Connected to page ${selectedIndex}</span>`;
    // Immediately update to show fresh state
    setTimeout(updateStatus, 100);
  }
};

// Disconnect from current page
document.getElementById("disconnect").onclick = async () => {
  const result = await api("/disconnect", "POST");
  document.getElementById("status").innerHTML = 'Disconnected';
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
  const result = await api("/fetch", "POST", { enabled: newState });
  
  if (!result.error) {
    document.getElementById("status").innerHTML = 
      `<span class="connected">Intercept ${result.enabled ? 'enabled' : 'disabled'}</span>`;
    // Update display immediately
    setTimeout(updateStatus, 100);
  } else {
    document.getElementById("status").innerHTML = 
      `<span class="error">Error: ${result.error}</span>`;
  }
};

// Update fetch status display based on server state
function updateFetchStatus(fetchEnabled, pausedCount = 0) {
  const statusSpan = document.getElementById("fetchStatus");
  const toggleBtn = document.getElementById("fetchToggle");
  
  if (fetchEnabled) {
    if (pausedCount > 0) {
      statusSpan.textContent = `ON (${pausedCount} paused)`;
    } else {
      statusSpan.textContent = "ON";
    }
    statusSpan.style.color = "#080";
    toggleBtn.classList.add("on");
  } else {
    statusSpan.textContent = "OFF";
    statusSpan.style.color = "#888";
    toggleBtn.classList.remove("on");
  }
}

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
      
      // Update fetch status from server state
      updateFetchStatus(status.fetch_enabled || false, status.paused_requests || 0);
    } else {
      // Not connected
      document.getElementById("status").innerHTML = 'Not connected';
      updateFetchStatus(false);
    }
  }
}

// Initialize on load
loadPages();
updateStatus();

// Poll status every 2 seconds to stay in sync with WebTap
setInterval(updateStatus, 2000);