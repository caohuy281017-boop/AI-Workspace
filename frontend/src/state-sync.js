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

  function optionalString(value) {
    if (value == null) return null;
    const normalized = String(value).trim();
    return normalized === '' ? null : normalized;
  }

  function optionalNumber(value) {
    if (value == null) return null;
    const normalized = String(value).trim();
    if (normalized === '') return null;
    const number = Number(normalized);
    return Number.isFinite(number) ? number : null;
  }

  function normalizeEditableLineItem(values = {}) {
    const item = {
      description: optionalString(values.description),
      quantity: optionalNumber(values.quantity),
      unit_price: optionalNumber(values.unit_price),
      amount: optionalNumber(values.amount),
    };
    return Object.values(item).every(value => value == null) ? null : item;
  }

  const api = {
    applyConfirmedUpdate,
    updateInvoiceStatus,
    normalizeLineItems,
    optionalString,
    optionalNumber,
    normalizeEditableLineItem,
  };

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  }
  if (globalScope) {
    globalScope.InvoiceStateSync = api;
    globalScope.StateSync = api;
  }
})(typeof window !== 'undefined' ? window : globalThis);
