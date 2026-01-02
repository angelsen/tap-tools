/**
 * Capture Controller
 * Handles body capture toggle and state updates.
 */

let client = null;
let toggle = null;
let onError = null;

export function init(c, callbacks = {}) {
  client = c;
  onError = callbacks.onError || console.error;

  toggle = document.getElementById("captureToggle");
  if (!toggle) return;

  toggle.onclick = async () => {
    if (!client || !client.state.connected) {
      onError("Connect to a page first");
      return;
    }

    try {
      const isEnabled = toggle.classList.contains("active");
      if (isEnabled) {
        await client.call("fetch.disable");
      } else {
        await client.call("fetch.enable", { rules: { capture: true } });
      }
    } catch (err) {
      onError(err);
    }
  };
}

export function update(state) {
  if (!toggle) return;

  const enabled = state.fetch?.enabled && state.fetch?.rules?.capture;
  const captureCount = state.fetch?.capture_count || 0;

  toggle.classList.toggle("active", enabled);
  toggle.textContent = enabled
    ? `Capture: On (${captureCount})`
    : "Capture: Off";
}
