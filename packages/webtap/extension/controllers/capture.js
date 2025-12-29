/**
 * Capture Controller
 * Handles the Capture toggle button for extension-side body recording.
 */

let client = null;
let onError = null;

export function init(c, callbacks = {}) {
  client = c;
  onError = callbacks.onError || console.error;

  const btn = document.getElementById("captureToggle");
  if (!btn) return;

  btn.onclick = async () => {
    const isEnabled = btn.classList.contains("active");
    const method = isEnabled ? "capture.disable" : "capture.enable";
    try {
      await client.call(method);
    } catch (err) {
      onError(err);
    }
  };
}

export function update(state) {
  const btn = document.getElementById("captureToggle");
  if (!btn) return;

  const enabled = state.fetch?.capture_enabled || false;
  btn.classList.toggle("active", enabled);
}
