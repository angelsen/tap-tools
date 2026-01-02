/**
 * General Utilities - Loading state and button lock helpers
 */

/**
 * Wrap async operation with table loading state
 * @param {DataTable} table - DataTable instance
 * @param {string} message - Loading message to display
 * @param {Function} asyncFn - Async function to execute
 * @returns {Promise<any>} Result from asyncFn
 */
export async function withTableLoading(table, message, asyncFn) {
  table.setLoading(message);
  try {
    return await asyncFn();
  } finally {
    table.clearLoading();
  }
}

/**
 * Create a button lock to prevent concurrent operations
 * @returns {Function} withLock(buttonId, asyncFn)
 */
export function createButtonLock() {
  let locked = false;
  return async function withLock(buttonId, asyncFn) {
    if (locked) return;
    const btn = document.getElementById(buttonId);
    const wasDisabled = btn?.disabled;
    if (btn) btn.disabled = true;
    locked = true;
    try {
      return await asyncFn();
    } finally {
      if (btn) btn.disabled = wasDisabled;
      locked = false;
    }
  };
}
