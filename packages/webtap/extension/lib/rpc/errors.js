/**
 * RPC Error Codes - Mirrors webtap/rpc/errors.py
 */

export const ErrorCode = {
  METHOD_NOT_FOUND: "METHOD_NOT_FOUND",
  INVALID_STATE: "INVALID_STATE",
  STALE_EPOCH: "STALE_EPOCH",
  INVALID_PARAMS: "INVALID_PARAMS",
  INTERNAL_ERROR: "INTERNAL_ERROR",
  NOT_CONNECTED: "NOT_CONNECTED",
};

export function isRetryable(code) {
  return code === ErrorCode.STALE_EPOCH;
}
