'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const {
  applyConfirmedUpdate,
  updateInvoiceStatus,
  normalizeLineItems,
  optionalString,
  optionalNumber,
  normalizeEditableLineItem,
} = require('../src/state-sync.js');


test('does not mutate target when persistence fails', async () => {
  const invoice = { status: 'needs_review', total: 100 };

  const ok = await applyConfirmedUpdate(
    invoice,
    { status: 'approved', total: 200 },
    async () => false,
  );

  assert.equal(ok, false);
  assert.deepEqual(invoice, { status: 'needs_review', total: 100 });
});


test('applies values after persistence succeeds', async () => {
  const invoice = { status: 'needs_review' };

  const ok = await applyConfirmedUpdate(
    invoice,
    { status: 'approved' },
    async () => true,
  );

  assert.equal(ok, true);
  assert.equal(invoice.status, 'approved');
});


test('does not mutate target when persistence throws', async () => {
  const invoice = { status: 'needs_review' };

  await assert.rejects(
    applyConfirmedUpdate(
      invoice,
      { status: 'approved' },
      async () => { throw new Error('network down'); },
    ),
    /network down/,
  );
  assert.equal(invoice.status, 'needs_review');
});


test('updateInvoiceStatus updates target with global STATE', async () => {
  global.STATE = {
    invoices: [
      { id: 'inv-1', status: 'needs_review', ext: { supplier: 'Old' } }
    ]
  };

  const ok = await updateInvoiceStatus(
    'inv-1',
    'approved',
    { ext: { supplier: 'New' }, status: 'approved' },
    async () => true
  );

  assert.equal(ok, true);
  assert.equal(global.STATE.invoices[0].status, 'approved');
  assert.equal(global.STATE.invoices[0].ext.supplier, 'New');

  delete global.STATE;
});


test('updateInvoiceStatus does not update target when persistence fails', async () => {
  global.STATE = {
    invoices: [
      { id: 'inv-2', status: 'needs_review', ext: { supplier: 'Original' } }
    ]
  };

  const ok = await updateInvoiceStatus(
    'inv-2',
    'approved',
    { ext: { supplier: 'Changed' }, status: 'approved' },
    async () => false
  );

  assert.equal(ok, false);
  assert.equal(global.STATE.invoices[0].status, 'needs_review');
  assert.equal(global.STATE.invoices[0].ext.supplier, 'Original');

  delete global.STATE;
});


test('does not fabricate a line item when extraction has none', () => {
  assert.deepEqual(normalizeLineItems(undefined), []);
  assert.deepEqual(normalizeLineItems(null), []);
  assert.deepEqual(normalizeLineItems('invalid'), []);
});


test('preserves extracted line items', () => {
  const items = [{ description: 'Real service', quantity: 1, amount: 100 }];
  assert.deepEqual(normalizeLineItems(items), items);
});


test('optional form values preserve missing data as null', () => {
  assert.equal(optionalString('  '), null);
  assert.equal(optionalString(' VND '), 'VND');
  assert.equal(optionalNumber(''), null);
  assert.equal(optionalNumber('not-a-number'), null);
  assert.equal(optionalNumber('0'), 0);
});


test('editable line items do not invent accounting values', () => {
  assert.equal(normalizeEditableLineItem({}), null);
  assert.deepEqual(
    normalizeEditableLineItem({ description: 'Dịch vụ', quantity: '', unit_price: '', amount: '0' }),
    { description: 'Dịch vụ', quantity: null, unit_price: null, amount: 0 },
  );
});
