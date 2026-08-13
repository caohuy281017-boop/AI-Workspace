'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

const { groups, rankTools, tools } = require('../src/tool-catalog.js');

test('catalog exposes all tools with user-facing guidance', () => {
  assert.equal(tools.length, 20);
  assert.equal(new Set(tools.map(tool => tool.id)).size, tools.length);

  for (const tool of tools) {
    assert.ok(tool.title.length >= 5, `${tool.id} needs a clear title`);
    assert.ok(tool.description.length >= 25, `${tool.id} needs an outcome description`);
    assert.ok(tool.useWhen.length >= 20, `${tool.id} needs a use case`);
    assert.ok(tool.example.includes('→'), `${tool.id} needs an input-to-output example`);
    assert.ok(tool.inputLabel && tool.outputLabel, `${tool.id} needs field labels`);
    assert.ok(groups.some(group => group.id === tool.group), `${tool.id} references an unknown group`);
  }
});

test('catalog groups are written as user jobs, not implementation jargon', () => {
  assert.deepEqual(groups.map(group => group.id), ['writing', 'lists', 'data', 'web']);
  for (const group of groups) {
    assert.ok(group.title.length >= 8);
    assert.ok(group.description.length >= 25);
  }
});

test('search ranks the tool that directly solves the requested job first', () => {
  const emailResults = rankTools(tools, 'email');
  assert.equal(emailResults[0].id, 'extract-contacts');
  assert.ok(!emailResults.some(tool => tool.id === 'word-count'));
  assert.equal(rankTools(tools, 'xóa trùng')[0].id, 'remove-duplicate-lines');
  assert.equal(rankTools(tools, 'đổi chữ')[0].id, 'case-converter');
  assert.equal(rankTools(tools, 'dọn danh sách khách hàng')[0].id, 'text-workflow');
});
