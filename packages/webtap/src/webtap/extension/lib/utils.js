/**
 * General Utilities - Loading state helpers
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
