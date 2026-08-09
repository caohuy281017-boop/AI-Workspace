'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const { applyConfirmedUpdate, normalizeLineItems } = require('../src/state-sync.js');


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


test('does not fabricate a line item when extraction has none', () => {
  assert.deepEqual(normalizeLineItems(undefined), []);
  assert.deepEqual(normalizeLineItems(null), []);
  assert.deepEqual(normalizeLineItems('invalid'), []);
});


test('preserves extracted line items', () => {
  const items = [{ description: 'Real service', quantity: 1, amount: 100 }];
  assert.deepEqual(normalizeLineItems(items), items);
});
