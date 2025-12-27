/**
 * Header Controller
 * Manages status indicator, error banner, event count
 */

export function updateStatus(text, state = "disconnected") {
  const status = document.getElementById("status");
  const statusText = status.querySelector(".status-text");

  status.classList.toggle("connected", state === "connected");
  status.classList.toggle("error", state === "error");

  statusText.textContent = text;
}

export function showError(message) {
  if (message instanceof Error) {
    message = message.message;
  }
  updateStatus(message, "error");
}

export function updateConnection(state) {
  if (state.connected) {
    updateStatus(`Connected (${state.events.total})`, "connected");
  } else if (!state.connected) {
    updateStatus("Disconnected", "disconnected");
  }
}

export function updateEventCount(count) {
  const status = document.getElementById("status");
  if (status.classList.contains("connected")) {
    const statusText = status.querySelector(".status-text");
    statusText.textContent = `Connected (${count})`;
  }
}

export function updateError(errors) {
  const banner = document.getElementById("errorBanner");
  const message = document.getElementById("errorMessage");

  // Handle both old format (single error) and new format (errors dict)
  if (errors && typeof errors === "object") {
    // New format: {target_id: {message, timestamp}}
    if (errors.message) {
      // Old format: {message, timestamp}
      message.textContent = errors.message;
      banner.classList.add("visible");
    } else {
      // New format: pick first error from dict
      const errorEntries = Object.entries(errors);
      if (errorEntries.length > 0) {
        const [targetId, errorData] = errorEntries[0];
        message.textContent = `${targetId}: ${errorData.message}`;
        banner.classList.add("visible");
      } else {
        banner.classList.remove("visible");
      }
    }
  } else {
    banner.classList.remove("visible");
  }
}
