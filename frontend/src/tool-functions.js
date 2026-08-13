'use strict';

(function exposeToolFunctions(root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.AIWorkspaceToolFunctions = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function createToolFunctions() {
  const lines = text => String(text).replace(/\r\n?/g, '\n').split('\n');
  const meaningfulLines = text => lines(text).map(line => line.trim()).filter(Boolean);

  function countText(text) {
    const value = String(text);
    const trimmed = value.trim();
    const words = trimmed ? trimmed.split(/\s+/u).length : 0;
    const lineCount = value ? lines(value).length : 0;
    const readingMinutes = words ? Math.max(1, Math.ceil(words / 220)) : 0;
    return `Từ: ${words}\nKý tự: ${value.length}\nKý tự (không khoảng trắng): ${value.replace(/\s/gu, '').length}\nDòng: ${lineCount}\nThời gian đọc: ~${readingMinutes} phút`;
  }

  function cleanText(text) {
    return lines(text)
      .map(line => line.trim().replace(/[ \t]+/g, ' '))
      .join('\n')
      .replace(/\n{3,}/g, '\n\n')
      .trim();
  }

  function removeVietnameseAccents(text) {
    return String(text)
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .replace(/đ/g, 'd')
      .replace(/Đ/g, 'D');
  }

  function toSlug(text) {
    return removeVietnameseAccents(text)
      .toLowerCase()
      .trim()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '');
  }

  function titleCase(text) {
    return String(text)
      .toLocaleLowerCase('vi')
      .replace(/(^|[\s-])\p{L}/gu, value => value.toLocaleUpperCase('vi'));
  }

  function sentenceCase(text) {
    return String(text)
      .toLocaleLowerCase('vi')
      .replace(/(^\s*|[.!?]\s+)\p{L}/gu, value => value.toLocaleUpperCase('vi'));
  }

  function convertCase(text, mode) {
    const value = String(text);
    if (mode === 'upper') return value.toLocaleUpperCase('vi');
    if (mode === 'lower') return value.toLocaleLowerCase('vi');
    if (mode === 'title') return titleCase(value);
    if (mode === 'sentence') return sentenceCase(value);
    throw new Error(`Kiểu chuyển chữ không được hỗ trợ: ${mode}`);
  }

  function decodeHtmlEntities(text) {
    const named = { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' ' };
    return String(text).replace(/&(#x[\da-f]+|#\d+|[a-z]+);/gi, (entity, code) => {
      if (code[0] === '#') {
        const radix = code[1].toLowerCase() === 'x' ? 16 : 10;
        const raw = radix === 16 ? code.slice(2) : code.slice(1);
        const point = Number.parseInt(raw, radix);
        try { return Number.isFinite(point) ? String.fromCodePoint(point) : entity; } catch (_err) { return entity; }
      }
      return named[code.toLowerCase()] ?? entity;
    });
  }

  function normalizeHtmlText(text) {
    return lines(String(text).replace(/\u00a0/g, ' '))
      .map(line => line.replace(/[ \t]+/g, ' ').trim())
      .filter(Boolean)
      .join('\n');
  }

  function htmlToTextWithDom(text) {
    const doc = new DOMParser().parseFromString(String(text), 'text/html');
    doc.querySelectorAll('script, style, noscript, template, svg').forEach(node => node.remove());
    const blockTags = new Set([
      'ADDRESS', 'ARTICLE', 'ASIDE', 'BLOCKQUOTE', 'DIV', 'DL', 'DT', 'DD',
      'FIELDSET', 'FIGCAPTION', 'FIGURE', 'FOOTER', 'FORM', 'H1', 'H2', 'H3',
      'H4', 'H5', 'H6', 'HEADER', 'HR', 'LI', 'MAIN', 'NAV', 'OL', 'P', 'PRE',
      'SECTION', 'TABLE', 'TBODY', 'THEAD', 'TFOOT', 'TR', 'UL',
    ]);
    let output = '';
    const appendBreak = () => { if (output && !output.endsWith('\n')) output += '\n'; };
    const walk = node => {
      if (node.nodeType === 3) {
        output += node.nodeValue || '';
        return;
      }
      if (node.nodeType !== 1) return;
      const tag = node.tagName;
      if (tag === 'BR') { output += '\n'; return; }
      if (blockTags.has(tag)) appendBreak();
      for (const child of node.childNodes) walk(child);
      if (tag === 'TD' || tag === 'TH') output += '\t';
      if (blockTags.has(tag)) appendBreak();
    };
    for (const child of doc.body.childNodes) walk(child);
    return normalizeHtmlText(output);
  }

  function htmlToTextFallback(text) {
    const blockPattern = 'address|article|aside|blockquote|div|dl|dt|dd|fieldset|figcaption|figure|footer|form|h[1-6]|header|hr|li|main|nav|ol|p|pre|section|table|tbody|thead|tfoot|tr|ul';
    const output = String(text)
      .replace(/<!--[\s\S]*?-->/g, '')
      .replace(/<(script|style|noscript|template|svg)\b[^>]*>[\s\S]*?<\/\1\s*>/gi, '')
      .replace(/<br\b[^>]*>/gi, '\n')
      .replace(new RegExp(`<\\/?(?:${blockPattern})\\b[^>]*>`, 'gi'), '\n')
      .replace(/<\/(?:td|th)\s*>/gi, '\t')
      .replace(/<[^>]+>/g, '');
    return normalizeHtmlText(decodeHtmlEntities(output));
  }

  function htmlToText(text) {
    return typeof DOMParser === 'function' ? htmlToTextWithDom(text) : htmlToTextFallback(text);
  }

  function markdownToText(text) {
    let value = String(text).replace(/\r\n?/g, '\n');
    value = value.replace(/^---\n[\s\S]*?\n---\n?/, '');
    value = value.replace(/^[ \t]*```[^\n]*\n?/gm, '').replace(/^[ \t]*~~~[^\n]*\n?/gm, '');
    value = value.replace(/!\[([^\]]*)\]\([^)]*\)/g, '$1');
    value = value.replace(/\[([^\]]+)\]\([^)]*\)/g, '$1');
    value = value.replace(/^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$/gm, '');
    value = value.replace(/^\s{0,3}#{1,6}\s+/gm, '');
    value = value.replace(/^[ \t]*>[ \t]?/gm, '');
    value = value.replace(/^[ \t]*(?:[-*+][ \t]+|\d+[.)][ \t]+)/gm, '');
    value = value.replace(/\*\*|__|~~/g, '');
    value = value.replace(/(^|[^\\])[*_](?=\S)|(?<=\S)[*_](?!\w)/g, '$1');
    value = value.replace(/`([^`]*)`/g, '$1');
    value = value.replace(/<br\s*\/?\s*>/gi, '\n').replace(/<[^>]+>/g, '');
    value = decodeHtmlEntities(value);
    return lines(value)
      .map(line => line.trim().replace(/[ \t]+/g, ' '))
      .join('\n')
      .replace(/\n{3,}/g, '\n\n')
      .trim();
  }

  function uniqueLines(text) {
    const seen = new Set();
    return meaningfulLines(text).filter(line => {
      if (seen.has(line)) return false;
      seen.add(line);
      return true;
    }).join('\n');
  }

  function reverseLines(text) {
    return meaningfulLines(text).reverse().join('\n');
  }

  function removeEmptyLines(text) {
    return meaningfulLines(text).join('\n');
  }

  function numberLines(text) {
    return meaningfulLines(text).map((line, index) => `${index + 1}. ${line}`).join('\n');
  }

  function sortLines(text, mode) {
    const values = meaningfulLines(text);
    const collator = new Intl.Collator('vi', { sensitivity: 'base', numeric: true });
    if (mode === 'asc') return values.sort(collator.compare).join('\n');
    if (mode === 'desc') return values.sort((a, b) => collator.compare(b, a)).join('\n');
    if (mode === 'length-asc') return values.sort((a, b) => a.length - b.length || collator.compare(a, b)).join('\n');
    if (mode === 'length-desc') return values.sort((a, b) => b.length - a.length || collator.compare(a, b)).join('\n');
    throw new Error(`Kiểu sắp xếp không được hỗ trợ: ${mode}`);
  }

  function detectDelimiter(text) {
    const counts = { ',': 0, ';': 0, '\t': 0 };
    let quoted = false;
    for (let index = 0; index < text.length; index += 1) {
      const char = text[index];
      if (char === '"') {
        if (quoted && text[index + 1] === '"') index += 1;
        else quoted = !quoted;
      } else if (!quoted && char === '\n') {
        break;
      } else if (!quoted && Object.hasOwn(counts, char)) {
        counts[char] += 1;
      }
    }
    return Object.entries(counts).sort((a, b) => b[1] - a[1])[0][0];
  }

  function parseDelimited(text, delimiter) {
    const rows = [];
    let row = [];
    let field = '';
    let quoted = false;
    const value = String(text).replace(/^\ufeff/, '').replace(/\r\n?/g, '\n');
    for (let index = 0; index < value.length; index += 1) {
      const char = value[index];
      if (char === '"') {
        if (quoted && value[index + 1] === '"') { field += '"'; index += 1; }
        else quoted = !quoted;
      } else if (char === delimiter && !quoted) {
        row.push(field);
        field = '';
      } else if (char === '\n' && !quoted) {
        row.push(field);
        rows.push(row);
        row = [];
        field = '';
      } else {
        field += char;
      }
    }
    row.push(field);
    rows.push(row);
    return rows.filter(fields => fields.some(item => item.trim() !== ''));
  }

  function splitCommaSeparated(text) {
    return parseDelimited(text, ',').flat().map(value => value.trim()).filter(Boolean).join('\n');
  }

  function joinLines(text, separator) {
    return meaningfulLines(text).join(separator);
  }

  function parseJson(text) {
    try { return JSON.parse(String(text)); }
    catch (error) { throw new Error(`JSON không hợp lệ: ${error.message}`); }
  }

  function formatJson(text) {
    return JSON.stringify(parseJson(text), null, 2);
  }

  function minifyJson(text) {
    return JSON.stringify(parseJson(text));
  }

  function csvToJson(text) {
    const value = String(text).replace(/^\ufeff/, '');
    if (!value.trim()) return '[]';
    const delimiter = detectDelimiter(value);
    const rows = parseDelimited(value, delimiter);
    if (!rows.length) return '[]';
    const rawHeaders = rows.shift();
    const usedHeaders = new Map();
    const headers = rawHeaders.map((header, index) => {
      const base = header.trim() || `column_${index + 1}`;
      const count = (usedHeaders.get(base) || 0) + 1;
      usedHeaders.set(base, count);
      return count === 1 ? base : `${base}_${count}`;
    });
    const records = rows.map(row => Object.fromEntries(headers.map((header, index) => [header, row[index] ?? ''])));
    return JSON.stringify(records, null, 2);
  }

  function uniqueMatches(values, key = value => value) {
    const seen = new Set();
    return values.filter(value => {
      const normalized = key(value);
      if (seen.has(normalized)) return false;
      seen.add(normalized);
      return true;
    });
  }

  function extractContacts(text, type) {
    const value = String(text);
    if (type === 'email') {
      const matches = value.match(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi) || [];
      return uniqueMatches(matches, item => item.toLocaleLowerCase('en')).join('\n');
    }
    if (type === 'phone') {
      const matches = [];
      const pattern = /(?:^|[^\d])((?:\+?84|0)(?:[ .-]?\d){9})(?!\d)/g;
      let match;
      while ((match = pattern.exec(value)) !== null) matches.push(match[1].trim());
      return uniqueMatches(matches, item => item.replace(/\D/g, '').replace(/^84/, '0')).join('\n');
    }
    if (type === 'url') {
      const matches = (value.match(/https?:\/\/[^\s<>"']+/gi) || [])
        .map(item => item.replace(/[),.;!?]+$/g, ''));
      return uniqueMatches(matches, item => item.toLocaleLowerCase('en')).join('\n');
    }
    throw new Error(`Loại liên hệ không được hỗ trợ: ${type}`);
  }

  function runTextWorkflow(text, mode) {
    const cleaned = cleanText(text);
    if (mode === 'clean') return cleaned;
    if (mode === 'dedupe') return uniqueLines(cleaned);
    if (mode === 'sort') return sortLines(uniqueLines(cleaned), 'asc');
    if (mode === 'slug') return meaningfulLines(uniqueLines(cleaned)).map(toSlug).join('\n');
    throw new Error(`Quy trình văn bản không được hỗ trợ: ${mode}`);
  }

  function transformUrl(text, mode) {
    try {
      if (mode === 'encode') return encodeURIComponent(String(text));
      if (mode === 'decode') return decodeURIComponent(String(text));
    } catch (error) {
      throw new Error(`URL mã hóa không hợp lệ: ${error.message}`);
    }
    throw new Error(`Thao tác URL không được hỗ trợ: ${mode}`);
  }

  function bytesToBinary(bytes) {
    let output = '';
    for (let index = 0; index < bytes.length; index += 0x8000) {
      output += String.fromCharCode(...bytes.subarray(index, index + 0x8000));
    }
    return output;
  }

  function transformBase64(text, mode) {
    const value = String(text);
    if (mode === 'encode') {
      if (typeof Buffer !== 'undefined') return Buffer.from(value, 'utf8').toString('base64');
      return btoa(bytesToBinary(new TextEncoder().encode(value)));
    }
    if (mode === 'decode') {
      const compact = value.replace(/\s/g, '');
      if (!/^[A-Za-z0-9+/]*={0,2}$/.test(compact) || compact.length % 4 === 1 || /=/.test(compact.slice(0, -2))) {
        throw new Error('Base64 không hợp lệ.');
      }
      const padded = compact.padEnd(Math.ceil(compact.length / 4) * 4, '=');
      try {
        const bytes = typeof Buffer !== 'undefined'
          ? Buffer.from(padded, 'base64')
          : Uint8Array.from(atob(padded), char => char.charCodeAt(0));
        return new TextDecoder('utf-8', { fatal: true }).decode(bytes);
      } catch (_error) {
        throw new Error('Base64 không hợp lệ hoặc không chứa văn bản UTF-8.');
      }
    }
    throw new Error(`Thao tác Base64 không được hỗ trợ: ${mode}`);
  }

  return {
    cleanText,
    convertCase,
    countText,
    csvToJson,
    extractContacts,
    formatJson,
    htmlToText,
    joinLines,
    markdownToText,
    minifyJson,
    numberLines,
    removeEmptyLines,
    removeVietnameseAccents,
    reverseLines,
    runTextWorkflow,
    sortLines,
    splitCommaSeparated,
    toSlug,
    transformBase64,
    transformUrl,
    uniqueLines,
  };
});
