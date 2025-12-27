/**
 * Intercept Controller
 * Handles request interception dropdown and state updates.
 */

import { Dropdown } from "../bind.js";

let client = null;
let dropdown = null;
let onError = null;

export function init(c, callbacks = {}) {
  client = c;
  onError = callbacks.onError || console.error;

  dropdown = new Dropdown("#interceptDropdown", {
    onSelect: async (mode) => {
      if (!client || !client.state.connected) {
        onError("Connect to a page first");
        return;
      }

      try {
        if (mode === "disabled") {
          await client.call("fetch.disable");
        } else {
          await client.call("fetch.enable", {
            request: true,
            response: mode === "response",
          });
        }
      } catch (err) {
        onError(err);
      }
    },
  });
}

export function update(state) {
  if (!dropdown) return;

  let mode = "disabled";
  if (state.fetch.enabled) {
    mode = state.fetch.response_stage ? "response" : "request";
  }

  dropdown.setActive(mode);

  const labels = { disabled: "Off", request: "Req", response: "Req+Res" };
  const paused = state.fetch.paused_count || 0;
  const pausedText = paused > 0 ? ` (${paused})` : "";
  dropdown.setText(`Intercept: ${labels[mode]}${pausedText}`);
  dropdown.toggle.classList.toggle("active", state.fetch.enabled);
}
