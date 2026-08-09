'use strict';

(function exposeStateSync(globalScope) {
  async function applyConfirmedUpdate(target, nextValues, persist) {
    const persisted = await persist(nextValues);
    if (persisted !== true) return false;
    Object.assign(target, nextValues);
    return true;
  }

  function normalizeLineItems(items) {
    return Array.isArray(items) ? items : [];
  }

  const api = { applyConfirmedUpdate, normalizeLineItems };

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  }
  if (globalScope) {
    globalScope.InvoiceStateSync = api;
  }
})(typeof window !== 'undefined' ? window : globalThis);
