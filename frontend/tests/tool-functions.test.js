'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');

const tools = require('../src/tool-functions.js');

test('word-count reports Vietnamese text consistently', () => {
  assert.equal(
    tools.countText('Xin chào\nViệt Nam'),
    'Từ: 4\nKý tự: 17\nKý tự (không khoảng trắng): 14\nDòng: 2\nThời gian đọc: ~1 phút',
  );
  assert.match(tools.countText(''), /Từ: 0[\s\S]*Dòng: 0/);
});

test('clean-text normalizes spaces without destroying paragraphs', () => {
  assert.equal(tools.cleanText('  Xin\t chào  \n\n\n  Việt Nam  '), 'Xin chào\n\nViệt Nam');
});

test('case-converter supports all four visible actions', () => {
  assert.equal(tools.convertCase('Xin Chào', 'upper'), 'XIN CHÀO');
  assert.equal(tools.convertCase('Xin Chào', 'lower'), 'xin chào');
  assert.equal(tools.convertCase('xin chào VIỆT NAM', 'title'), 'Xin Chào Việt Nam');
  assert.equal(tools.convertCase('XIN CHÀO. VIỆT NAM!', 'sentence'), 'Xin chào. Việt nam!');
});

test('remove-accents handles Vietnamese d characters', () => {
  assert.equal(tools.removeVietnameseAccents('Đường đến Đà Nẵng'), 'Duong den Da Nang');
});

test('html-to-text preserves readable blocks and removes executable content', () => {
  const input = '<h1>Tiêu đề</h1><p>Xin <strong>chào</strong><br>Việt Nam &amp; bạn</p>'
    + '<ul><li>Một</li><li>Hai</li></ul><script>alert(1)</script><style>.x{}</style>';
  assert.equal(tools.htmlToText(input), 'Tiêu đề\nXin chào\nViệt Nam & bạn\nMột\nHai');
});

test('markdown-to-text removes markup but keeps useful content and line breaks', () => {
  const input = '# Tiêu đề\n\n- **Một**\n- [Hai](https://example.com)\n\n![Ảnh hóa đơn](invoice.png)';
  assert.equal(tools.markdownToText(input), 'Tiêu đề\n\nMột\nHai\n\nẢnh hóa đơn');
});

test('remove-duplicate-lines keeps the first non-empty occurrence', () => {
  assert.equal(tools.uniqueLines(' An \nBình\nAn\n\nBình '), 'An\nBình');
});

test('sort-lines ignores blank rows and supports every order', () => {
  assert.equal(tools.sortLines('cam\n\ntáo\nổi', 'asc'), 'cam\nổi\ntáo');
  assert.equal(tools.sortLines('A\nC\nB', 'desc'), 'C\nB\nA');
  assert.equal(tools.sortLines('bbb\na\ncc', 'length-asc'), 'a\ncc\nbbb');
  assert.equal(tools.sortLines('a\nccc\nbb', 'length-desc'), 'ccc\nbb\na');
});

test('reverse-lines reverses meaningful rows only', () => {
  assert.equal(tools.reverseLines('Một\n\n Hai '), 'Hai\nMột');
});

test('remove-empty-lines removes whitespace-only rows', () => {
  assert.equal(tools.removeEmptyLines('Một\n \nHai'), 'Một\nHai');
});

test('number-lines trims and numbers meaningful rows', () => {
  assert.equal(tools.numberLines(' Một \n\nHai'), '1. Một\n2. Hai');
});

test('join-split-lines joins rows and parses quoted comma values', () => {
  assert.equal(tools.joinLines(' Một \n\nHai', '; '), 'Một; Hai');
  assert.equal(tools.joinLines('Một\nHai', ', '), 'Một, Hai');
  assert.equal(tools.splitCommaSeparated('Một,"Hai, Ba",Bốn'), 'Một\nHai, Ba\nBốn');
});

test('text-workflow combines cleaning, deduplication, sorting and slugging', () => {
  const input = '  Đỏ  \nXanh\nĐỏ';
  assert.equal(tools.runTextWorkflow('  Một   dòng  ', 'clean'), 'Một dòng');
  assert.equal(tools.runTextWorkflow(input, 'dedupe'), 'Đỏ\nXanh');
  assert.equal(tools.runTextWorkflow('Xanh\nĐỏ\nXanh', 'sort'), 'Đỏ\nXanh');
  assert.equal(tools.runTextWorkflow(input, 'slug'), 'do\nxanh');
});

test('json-format validates and pretty prints JSON', () => {
  assert.equal(tools.formatJson('{"name":"An"}'), '{\n  "name": "An"\n}');
  assert.throws(() => tools.formatJson('{name}'), /JSON không hợp lệ/);
});

test('json-minify validates and removes insignificant whitespace', () => {
  assert.equal(tools.minifyJson('{ "ok": true }'), '{"ok":true}');
});

test('csv-to-json handles quoted commas, multiline cells and delimiter detection', () => {
  const commaCsv = 'name,note\nAn,"Xin, chào"\nBình,"Dòng 1\nDòng 2"';
  assert.deepEqual(JSON.parse(tools.csvToJson(commaCsv)), [
    { name: 'An', note: 'Xin, chào' },
    { name: 'Bình', note: 'Dòng 1\nDòng 2' },
  ]);
  assert.deepEqual(JSON.parse(tools.csvToJson('\ufeffname;city\nAn;Huế')), [{ name: 'An', city: 'Huế' }]);
});

test('extract-contacts returns unique emails, Vietnamese phones and clean URLs', () => {
  const input = 'Mail A@Example.com, a@example.com. Gọi +84 912 345 678 hoặc 0901.234.567. Xem https://example.com/a).';
  assert.equal(tools.extractContacts(input, 'email'), 'A@Example.com');
  assert.equal(tools.extractContacts(input, 'phone'), '+84 912 345 678\n0901.234.567');
  assert.equal(tools.extractContacts(input, 'url'), 'https://example.com/a');
});

test('slug creates an ASCII URL path', () => {
  assert.equal(tools.toSlug('  Đọc Hóa Đơn 2026! '), 'doc-hoa-don-2026');
});

test('url-encode round trips Vietnamese Unicode', () => {
  const encoded = tools.transformUrl('Xin chào?', 'encode');
  assert.equal(encoded, 'Xin%20ch%C3%A0o%3F');
  assert.equal(tools.transformUrl(encoded, 'decode'), 'Xin chào?');
});

test('base64 round trips Vietnamese Unicode and rejects malformed input', () => {
  const encoded = tools.transformBase64('Tiếng Việt', 'encode');
  assert.equal(tools.transformBase64(encoded, 'decode'), 'Tiếng Việt');
  assert.throws(() => tools.transformBase64('%%%khong-hop-le', 'decode'), /Base64 không hợp lệ/);
});
