'use strict';

(function exposeStateSync(globalScope) {
  async function applyConfirmedUpdate(target, nextValues, persist) {
    const persisted = await persist(nextValues);
    if (persisted !== true) return false;
    Object.assign(target, nextValues);
    return true;
  }

  async function updateInvoiceStatus(id, newStatus, patchValues, persist) {
    const inv = (typeof STATE !== 'undefined' && STATE.invoices)
      ? STATE.invoices.find(i => i.id === id)
      : null;
    const target = inv || {};
    const persisted = await persist();
    if (persisted !== true) return false;

    if (patchValues) {
      if (patchValues.ext && target.ext) {
        Object.assign(target.ext, patchValues.ext);
      }
      if (patchValues.status) {
        target.status = patchValues.status;
      } else if (newStatus) {
        target.status = newStatus;
      }
    } else if (newStatus) {
      target.status = newStatus;
    }
    return true;
  }

  function normalizeLineItems(items) {
    return Array.isArray(items) ? items : [];
  }

  const api = { applyConfirmedUpdate, updateInvoiceStatus, normalizeLineItems };

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  }
  if (globalScope) {
    globalScope.InvoiceStateSync = api;
    globalScope.StateSync = api;
  }
})(typeof window !== 'undefined' ? window : globalThis);

