'use strict';
// ══════════════════════════════════════════════════════
//   AI WORKSPACE — FRONTEND SPA (PRODUCTION HARDENED)
//   XSS Safe, Dynamic Line-Items Editor, Gemini AI Vision Settings
// ══════════════════════════════════════════════════════

const API_BASE = window.location.origin;

// ── XSS Sanitization Helper ────────────────────────────
function escapeHtml(str) {
  if (str == null) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function normalizeLineItems(items) {
  if (Array.isArray(items) && items.length > 0) {
    return items.map((it) => {
      if (typeof it === 'string') {
        return { desc: it, qty: 1, price: 0, amt: 0 };
      }
      return {
        desc: it.description || it.desc || 'Hàng hóa / Dịch vụ',
        qty: parseFloat(it.quantity || it.qty || 1) || 1,
        price: parseFloat(it.unit_price || it.price || 0) || 0,
        amt: parseFloat(it.amount || it.amt || 0) || 0,
      };
    });
  }
  return [];
}

// ── Theme Management ───────────────────────────────────
(function initTheme() {
  const saved = localStorage.getItem('aiws-theme') || 'light';
  applyTheme(saved, true);
})();

function applyTheme(theme, silent) {
  const html = document.documentElement;
  if (theme === 'dark') {
    html.setAttribute('data-theme', 'dark');
  } else {
    html.removeAttribute('data-theme');
  }
  localStorage.setItem('aiws-theme', theme);
  if (!silent) updateThemeButton(theme);
}

function updateThemeButton(theme) {
  const iconDark  = document.getElementById('icon-dark');
  const iconLight = document.getElementById('icon-light');
  const label     = document.getElementById('theme-label');
  if (!iconDark || !iconLight || !label) return;
  if (theme === 'dark') {
    iconDark.style.display  = 'none';
    iconLight.style.display = '';
    label.textContent = 'Sáng';
  } else {
    iconDark.style.display  = '';
    iconLight.style.display = 'none';
    label.textContent = 'Tối';
  }
}

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
  const next = current === 'dark' ? 'light' : 'dark';
  applyTheme(next);
}

// ── State ──────────────────────────────────────────────
const STATE = {
  view: 'hub',
  filter: 'all',
  filterType: 'all',  // 'all' | 'dau_vao' | 'dau_ra' | 'khac'
  query: '',
  inspecting: null,
  currentBatchId: null,
  invoices: [],
  customFields: []
};

// ── Apps directory ─────────────────────────────────────
const APPS = [
  { id:'hub',         icon:'🏠', title:'Trang chủ',                  desc:'Hub tổng quan tất cả công cụ' },
  { id:'accounting',  icon:'🧾', title:'Xử lý lô Hóa đơn',           desc:'Batch invoice AI extraction & XLSX export' },
  { id:'translator',  icon:'📄', title:'Dịch tài liệu',              desc:'PDF/DOCX/PPTX translation with layout preserved' },
  { id:'meeting',     icon:'🎙️', title:'Biên bản Cuộc họp',          desc:'Audio → Transcript, Summary, Action Items' },
  { id:'settings',    icon:'⚙️', title:'Cấu hình AI Engine',         desc:'Gemini, OpenAI, Ollama configuration' },
];

// ── Formatters ─────────────────────────────────────────
function fmtMoney(v, cur = 'VND') {
  if (v == null || isNaN(v)) return '—';
  return cur === 'USD'
    ? '$' + Number(v).toLocaleString('en-US', { minimumFractionDigits: 2 })
    : Number(v).toLocaleString('vi-VN') + ' ₫';
}

// ── View switching ─────────────────────────────────────
function switchView(id) {
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  const target = document.getElementById('view-' + id);
  if (target) target.classList.add('active');

  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  const navItem = document.getElementById('nav-' + id);
  if (navItem) navItem.classList.add('active');

  const app = APPS.find(a => a.id === id);
  const bc = document.getElementById('breadcrumb');
  if (app) {
    if (id === 'hub') {
      bc.innerHTML = '<span>AI Workspace</span><span class="sep">/</span><span class="cur">Trang chủ</span>';
    } else {
      bc.innerHTML = `<span onclick="switchView('hub')" style="cursor:pointer;">AI Workspace</span><span class="sep">/</span><span class="cur">${escapeHtml(app.icon)} ${escapeHtml(app.title)}</span>`;
    }
  }

  STATE.view = id;
  const bar = document.getElementById('export-bar');
  if (bar) bar.style.display = id === 'accounting' ? 'flex' : 'none';

  if (id === 'settings') {
    const gKeyInput = document.getElementById('cfg-gemini-key');
    if (gKeyInput) gKeyInput.value = localStorage.getItem('GEMINI_API_KEY') || '';
    const oKeyInput = document.getElementById('cfg-openai-key');
    if (oKeyInput) oKeyInput.value = localStorage.getItem('OPENAI_API_KEY') || '';
    updateAiEngineCards(localStorage.getItem('AI_PROVIDER') || 'gemini');
    loadCustomFields();
    renderColumnLabelSettings();
  }

  closeSearch();
}

// ── Stats recalc ───────────────────────────────────────
function recalcStats() {
  const invs = STATE.invoices;
  const approved = invs.filter(i => i.status === 'approved');
  const review   = invs.filter(i => i.status === 'needs_review');
  const sumVND   = invs.filter(i => i.ext.currency === 'VND').reduce((s, i) => s + (i.ext.total || 0), 0);
  const dauVao   = invs.filter(i => i.invoice_type === 'dau_vao');
  const dauRa    = invs.filter(i => i.invoice_type === 'dau_ra');

  setText('s-total',        invs.length);
  setText('s-review',       review.length);
  setText('s-approved',     approved.length);
  setText('s-total-amount', fmtMoney(sumVND, 'VND'));
  setText('s-dau-vao',      dauVao.length);
  setText('s-dau-ra',       dauRa.length);
  setText('badge-review',   review.length > 0 ? review.length : '');

  const exportLabel = document.getElementById('export-bar-label');
  if (exportLabel) exportLabel.textContent = `${approved.length} hóa đơn đã duyệt sẵn sàng xuất Excel`;
}

function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

// ── Render invoice table (XSS Protected) ───────────────
function renderTable() {
  const tbody = document.getElementById('inv-tbody');
  if (!tbody) return;

  const q = STATE.query.toLowerCase();
  const f = STATE.filter;
  const ft = STATE.filterType;
  const visibleCustomFields = STATE.customFields.filter(field => field.visible_in_list);
  renderCustomFieldHeaders(visibleCustomFields);

  const INVOICE_TYPE_LABELS = {
    'dau_vao': { label: 'Đầu vào', cls: 'badge-info' },
    'dau_ra':  { label: 'Đầu ra',  cls: 'badge-ok'   },
    'khac':    { label: 'Khác',    cls: 'badge-warn'  },
  };

  const list = STATE.invoices.filter(inv => {
    if (f === 'approved'     && inv.status !== 'approved')     return false;
    if (f === 'needs_review' && inv.status !== 'needs_review') return false;
    if (ft !== 'all' && (inv.invoice_type || 'dau_vao') !== ft) return false;
    if (q) {
      const customText = Object.values(inv.ext.customFields || {}).join(' ');
      const noteText = inv.note || '';
      return (inv.ext.supplier + inv.ext.num + inv.ext.tax + inv.file + customText + noteText).toLowerCase().includes(q);
    }
    return true;
  });

  if (list.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8" style="text-align:center;padding:32px;color:var(--t-3);">Không tìm thấy hóa đơn nào. Tải lên file PDF/ảnh để bắt đầu.</td></tr>`;
    return;
  }

  tbody.innerHTML = list.map(inv => {
    const e = inv.ext;
    const badge = inv.status === 'approved'
      ? `<span class="badge badge-ok"><span class="badge-dot"></span>Đã duyệt</span>`
      : `<span class="badge badge-warn"><span class="badge-dot"></span>Cần soi</span>`;

    const typeInfo = INVOICE_TYPE_LABELS[inv.invoice_type || 'dau_vao'] || INVOICE_TYPE_LABELS['dau_vao'];
    const typeBadge = `<span class="badge ${typeInfo.cls}" style="font-size:.68rem;">${typeInfo.label}</span>`;

    const warningsText = (inv.warnings || []).map(w => escapeHtml(w)).join('\n');
    const warnIcon = inv.warnings && inv.warnings.length
      ? `<span title="${warningsText}" style="margin-left:6px; cursor:help;">⚠️</span>` : '';

    const approveBtn = inv.status === 'needs_review'
      ? `<button class="btn btn-ghost btn-sm" onclick="approveInv('${escapeHtml(inv.batch_id)}','${escapeHtml(inv.id)}')">✓ Duyệt</button>` : '';

    const customCells = visibleCustomFields.map(field => {
      const value = (e.customFields || {})[field.code];
      return `<td>${escapeHtml(value ?? '—')}</td>`;
    }).join('');

    return `<tr>
      <td>
        <div style="font-weight:500; max-width:180px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${escapeHtml(inv.file)}">${escapeHtml(inv.file)}</div>
        <div style="font-size:.72rem; color:var(--t-3); margin-top:2px;">${typeBadge}</div>
      </td>
      <td>
        <span class="cell-edit" onclick="editCell('${escapeHtml(inv.id)}','supplier',this)">${escapeHtml(e.supplier) || '<em style="color:var(--t-3)">Chưa có</em>'}</span>
        ${warnIcon}
      </td>
      <td><span class="cell-edit" onclick="editCell('${escapeHtml(inv.id)}','num',this)">${escapeHtml(e.num) || '—'}</span></td>
      <td style="white-space:nowrap;">${escapeHtml(e.date) || '—'}</td>
      <td style="font-weight:600; color:var(--c-brand); white-space:nowrap;">${fmtMoney(e.total, e.currency)}</td>
      ${customCells}
      <td>${badge}</td>
      <td>
        <div style="display:flex; gap:6px;">
          <button class="btn btn-ghost btn-sm" onclick="openInspector('${escapeHtml(inv.id)}')">🔍 Soi</button>
          ${approveBtn}
          <button class="btn btn-ghost btn-sm" onclick="deleteInv('${escapeHtml(inv.batch_id)}','${escapeHtml(inv.id)}')" style="color:var(--c-warn);" title="Xóa hóa đơn này">🗑</button>
        </div>
      </td>
    </tr>`;
  }).join('');
}

// ── Backend API Calls ──────────────────────────────────

function renderCustomFieldHeaders(fields) {
  const row = document.querySelector('.data-table thead tr');
  if (!row) return;
  row.querySelectorAll('.custom-field-header').forEach(header => header.remove());
  const statusHeader = row.children[row.children.length - 2];
  fields.forEach(field => {
    const header = document.createElement('th');
    header.className = 'custom-field-header';
    header.textContent = field.name;
    row.insertBefore(header, statusHeader);
  });
}

async function loadBatchesFromBackend() {
  try {
    const res = await fetch(`${API_BASE}/api/v1/accounting/batches`);
    if (!res.ok) return;
    const data = await res.json();
    STATE.invoices = [];
    STATE.currentBatchId = null;

    if (data.batches && data.batches.length) {
      data.batches.forEach(b => {
        if (!STATE.currentBatchId) STATE.currentBatchId = b.batch_id;
        b.items.forEach(item => {
          const ext = item.extraction || {};
          STATE.invoices.push({
            id: item.file_id,
            batch_id: b.batch_id,
            file: item.file_name,
            status: item.status || 'needs_review',
            invoice_type: item.invoice_type || 'dau_vao',
            note: item.note || '',
            warnings: item.warnings || [],
            ext: {
              supplier: ext.supplier_name || 'Nhà cung cấp chưa xác định',
              tax: ext.supplier_tax_id || '',
              num: ext.invoice_number || '—',
              date: ext.invoice_date || '—',
              currency: ext.currency || 'VND',
              sub: ext.subtotal || 0,
              vat: ext.tax_amount || 0,
              total: ext.total_amount || 0,
              items: normalizeLineItems(ext.items),
              customFields: ext.custom_fields || {}
            }
          });
        });
      });
    }
    recalcStats();
    renderTable();
  } catch (err) {
    console.warn("Backend API not reachable:", err);
  }
}

async function uploadRealFiles(files) {
  if (!files || !files.length) return;

  const dropZoneText = document.querySelector('#drop-zone h3');
  const originalText = dropZoneText ? dropZoneText.textContent : 'Kéo thả lô file Hóa đơn vào đây';
  if (dropZoneText) dropZoneText.textContent = '⏳ AI đang đọc & trích xuất hóa đơn...';

  const formData = new FormData();
  for (let i = 0; i < files.length; i++) {
    formData.append('files', files[i]);
  }

  const headers = {};
  const activeProvider = localStorage.getItem('AI_PROVIDER') || 'gemini';
  headers['X-LLM-Provider'] = activeProvider;

  const geminiKey = localStorage.getItem('GEMINI_API_KEY');
  if (geminiKey) {
    headers['X-Gemini-API-Key'] = geminiKey;
  }
  const openaiKey = localStorage.getItem('OPENAI_API_KEY');
  if (openaiKey) {
    headers['X-OpenAI-API-Key'] = openaiKey;
  }

  try {
    const res = await fetch(`${API_BASE}/api/v1/accounting/batches`, {
      method: 'POST',
      headers: headers,
      body: formData
    });

    if (!res.ok) throw new Error(`Upload failed: ${res.statusText}`);
    const batch = await res.json();
    STATE.currentBatchId = batch.batch_id;

      batch.items.forEach(item => {
      const ext = item.extraction || {};
      STATE.invoices.unshift({
        id: item.file_id,
        batch_id: batch.batch_id,
        file: item.file_name,
        status: item.status || 'needs_review',
        invoice_type: item.invoice_type || 'dau_vao',
        note: item.note || '',
        warnings: item.warnings || [],
        ext: {
          supplier: ext.supplier_name || 'Nhà cung cấp chưa xác định',
          tax: ext.supplier_tax_id || '',
          num: ext.invoice_number || '—',
          date: ext.invoice_date || '—',
          currency: ext.currency || 'VND',
          sub: ext.subtotal || 0,
          vat: ext.tax_amount || 0,
          total: ext.total_amount || 0,
          items: normalizeLineItems(ext.items),
          customFields: ext.custom_fields || {}
        }
      });
    });

    recalcStats();
    renderTable();
  } catch (err) {
    alert("Không thể tải hóa đơn lên backend API: " + err.message);
  } finally {
    if (dropZoneText) dropZoneText.textContent = originalText;
  }
}

async function updateInvoiceOnBackend(batchId, fileId, updates) {
  try {
    const res = await fetch(`${API_BASE}/api/v1/accounting/batches/${batchId}/items/${fileId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updates)
    });
    if (!res.ok) {
      const errData = await res.json();
      throw new Error(errData.detail || "Cập nhật backend thất bại");
    }
    return true;
  } catch (err) {
    alert("⚠️ Lỗi đồng bộ với backend: " + err.message);
    return false;
  }
}

// ── Inline cell editing ────────────────────────────────
function editCell(id, field, el) {
  const inv = STATE.invoices.find(i => i.id === id);
  if (!inv) return;
  const cur = inv.ext[field] || '';
  const input = document.createElement('input');
  input.type = 'text'; input.value = cur;
  input.style.cssText = 'background:var(--c-surface);border:1px solid var(--c-brand);border-radius:5px;padding:4px 8px;color:var(--t-1);font-size:.85rem;width:160px;outline:none;';
  el.innerHTML = ''; el.appendChild(input); input.focus();
  const save = async () => {
    const oldVal = inv.ext[field];
    inv.ext[field] = input.value;
    const backendKey = field === 'supplier' ? 'supplier_name' : field === 'num' ? 'invoice_number' : field;
    const ok = await updateInvoiceOnBackend(inv.batch_id, inv.id, { [backendKey]: input.value });
    if (!ok) inv.ext[field] = oldVal;
    renderTable();
  };
  input.addEventListener('blur', save);
  input.addEventListener('keydown', e => { if (e.key === 'Enter') save(); });
}

// ── Approve single ─────────────────────────────────────
async function approveInv(batchId, id) {
  const inv = STATE.invoices.find(i => i.id === id);
  if (!inv) return;
  const ok = await window.StateSync.updateInvoiceStatus(
    inv.id,
    'approved',
    { status: 'approved' },
    () => updateInvoiceOnBackend(batchId, id, { status: 'approved' })
  );
  if (ok) {
    recalcStats();
    renderTable();
  }
}

// ── Approve all ────────────────────────────────────────
async function approveAll() {
  let failedCount = 0;
  for (const inv of STATE.invoices) {
    if (inv.status !== 'approved') {
      const ok = await window.StateSync.updateInvoiceStatus(
        inv.id,
        'approved',
        { status: 'approved' },
        () => updateInvoiceOnBackend(inv.batch_id, inv.id, { status: 'approved' })
      );
      if (!ok) failedCount += 1;
    }
  }
  recalcStats();
  renderTable();
  if (failedCount > 0) {
    alert(`${failedCount} hóa đơn chưa được duyệt vì không thể đồng bộ với backend.`);
  }
}

// ── Delete invoice ──────────────────────────────────────
async function deleteInv(batchId, id) {
  if (!confirm('Xóa hóa đơn này khỏi hệ thống? Hành động không thể hoàn tác.')) return;
  try {
    const res = await fetch(`${API_BASE}/api/v1/accounting/batches/${batchId}/items/${id}`, {
      method: 'DELETE',
    });
    if (!res.ok && res.status !== 204) {
      const err = await res.json().catch(() => ({ detail: 'Lỗi không xác định' }));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }
    // Remove from STATE
    STATE.invoices = STATE.invoices.filter(i => i.id !== id);
    recalcStats();
    renderTable();
  } catch (err) {
    alert('⚠️ Không thể xóa hóa đơn: ' + err.message);
  }
}

// ── Filter by invoice type ──────────────────────────────
function filterByType(type) {
  STATE.filterType = type;
  document.querySelectorAll('.type-pill').forEach(p => {
    p.classList.toggle('active', p.dataset.t === type);
  });
  renderTable();
}


// ── Line Items Editor ──────────────────────────────────
function addLineItemRow(itemData = {}) {
  const ll = document.getElementById('line-items-list');
  if (!ll) return;

  const desc = itemData.desc || itemData.description || '';
  const qty  = itemData.qty || itemData.quantity || 1;
  const price = itemData.price || itemData.unit_price || 0;
  const amt  = itemData.amt || itemData.amount || (qty * price);

  const row = document.createElement('div');
  row.className = 'line-item-row';
  row.style.cssText = 'display:grid;grid-template-columns:2fr 1fr 1fr 1fr 30px;gap:8px;align-items:center;';
  row.innerHTML = `
    <input type="text"   class="field-input item-desc"  value="${escapeHtml(desc)}"  placeholder="Tên hàng hóa/dịch vụ" style="font-size:.8rem; padding:7px 10px;">
    <input type="number" class="field-input item-qty"   value="${escapeHtml(qty)}"   placeholder="SL"                   style="font-size:.8rem; padding:7px 10px;">
    <input type="number" class="field-input item-price" value="${escapeHtml(price)}" placeholder="Đơn giá"              style="font-size:.8rem; padding:7px 10px;">
    <input type="number" class="field-input item-amt"   value="${escapeHtml(amt)}"   placeholder="Thành tiền"           style="font-size:.8rem; padding:7px 10px; color:var(--c-brand); font-weight:600;">
    <button class="btn btn-ghost btn-sm" onclick="this.parentElement.remove(); recalcInspectorTotals();" style="padding:4px; color:var(--c-warn);" title="Xóa dòng này">✕</button>
  `;
  ll.appendChild(row);

  const qtyInput   = row.querySelector('.item-qty');
  const priceInput = row.querySelector('.item-price');
  const amtInput   = row.querySelector('.item-amt');

  const calc = () => {
    const q = parseFloat(qtyInput.value) || 0;
    const p = parseFloat(priceInput.value) || 0;
    amtInput.value = (q * p).toFixed(0);
    recalcInspectorTotals();
  };

  qtyInput.addEventListener('input', calc);
  priceInput.addEventListener('input', calc);
  amtInput.addEventListener('input', recalcInspectorTotals);
}

function recalcInspectorTotals() {
  const rows = document.querySelectorAll('#line-items-list .line-item-row');
  let subtotal = 0;
  rows.forEach(r => {
    const amt = parseFloat(r.querySelector('.item-amt').value) || 0;
    subtotal += amt;
  });
  if (subtotal > 0) {
    const vat = Math.round(subtotal * 0.08);
    const total = subtotal + vat;
    setVal('f-subtotal', subtotal);
    setVal('f-vat', vat);
    setVal('f-total', total);
  }
}

// ── Custom fields ─────────────────────────────────────
async function loadCustomFields() {
  const res = await fetch(`${API_BASE}/api/v1/accounting/settings/custom-fields`);
  if (!res.ok) return;
  STATE.customFields = (await res.json()).fields || [];
  renderCustomFieldsSettings();
  renderTable();
}

function renderCustomFieldsSettings() {
  const list = document.getElementById('custom-fields-list');
  if (!list) return;
  if (!STATE.customFields.length) {
    list.innerHTML = '<div class="custom-fields-empty">Chưa có trường tùy chỉnh.</div>';
    return;
  }
  list.innerHTML = STATE.customFields.map(field => `
    <div class="custom-field-card" draggable="true" data-code="${escapeHtml(field.code)}">
      <div class="drag-handle" title="Kéo để đổi thứ tự">↕</div>
      <div class="custom-field-main">
        <div class="custom-field-grid">
          <input class="field-input cf-name" value="${escapeHtml(field.name)}" aria-label="Tên trường">
          <select class="field-input cf-type">
            <option value="string" ${field.field_type === 'string' ? 'selected' : ''}>Văn bản</option>
            <option value="number" ${field.field_type === 'number' ? 'selected' : ''}>Số</option>
            <option value="boolean" ${field.field_type === 'boolean' ? 'selected' : ''}>Có/Không</option>
          </select>
          <code>${escapeHtml(field.code)}</code>
        </div>
        <input class="field-input cf-prompt" value="${escapeHtml(field.llm_prompt)}" placeholder="Prompt cho AI (có thể để trống)">
        <div class="custom-field-options">
          <label><input type="checkbox" class="cf-analysis" ${field.visible_in_analysis ? 'checked' : ''}> Hiện khi soi</label>
          <label><input type="checkbox" class="cf-list" ${field.visible_in_list ? 'checked' : ''}> Hiện trong bảng</label>
          <label><input type="checkbox" class="cf-required" ${field.is_required ? 'checked' : ''}> Bắt buộc</label>
        </div>
      </div>
      <div class="custom-field-actions">
        <button class="btn btn-ghost btn-sm" onclick="saveCustomField('${escapeHtml(field.code)}')">Lưu</button>
        <button class="btn btn-ghost btn-sm danger" onclick="deleteCustomField('${escapeHtml(field.code)}')">Xóa</button>
      </div>
    </div>`).join('');
  bindCustomFieldDragDrop();
}

async function createCustomField() {
  const name = getVal('cf-new-name').trim();
  const code = getVal('cf-new-code').trim().toLowerCase();
  if (!name || !code) return alert('Vui lòng nhập tên và mã trường.');
  const res = await fetch(`${API_BASE}/api/v1/accounting/settings/custom-fields`, {
    method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify({name, code, field_type:getVal('cf-new-type')})
  });
  if (!res.ok) return alert((await res.json()).detail || 'Không thể tạo trường.');
  setVal('cf-new-name', ''); setVal('cf-new-code', '');
  await loadCustomFields();
}

async function saveCustomField(code) {
  const card = document.querySelector(`.custom-field-card[data-code="${CSS.escape(code)}"]`);
  const body = {
    name: card.querySelector('.cf-name').value.trim(),
    field_type: card.querySelector('.cf-type').value,
    llm_prompt: card.querySelector('.cf-prompt').value.trim(),
    visible_in_analysis: card.querySelector('.cf-analysis').checked,
    visible_in_list: card.querySelector('.cf-list').checked,
    is_required: card.querySelector('.cf-required').checked
  };
  const res = await fetch(`${API_BASE}/api/v1/accounting/settings/custom-fields/${encodeURIComponent(code)}`, {
    method:'PATCH', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)
  });
  if (!res.ok) return alert('Không thể lưu trường.');
  await loadCustomFields();
}

async function deleteCustomField(code) {
  if (!confirm('Xóa định nghĩa trường này? Giá trị cũ trong chứng từ vẫn được giữ.')) return;
  const res = await fetch(`${API_BASE}/api/v1/accounting/settings/custom-fields/${encodeURIComponent(code)}`, {method:'DELETE'});
  if (!res.ok) return alert('Không thể xóa trường.');
  await loadCustomFields();
}

function bindCustomFieldDragDrop() {
  let dragged = null;
  document.querySelectorAll('.custom-field-card').forEach(card => {
    card.addEventListener('dragstart', () => { dragged = card; card.classList.add('dragging'); });
    card.addEventListener('dragend', async () => {
      card.classList.remove('dragging');
      const codes = [...document.querySelectorAll('.custom-field-card')].map(el => el.dataset.code);
      await fetch(`${API_BASE}/api/v1/accounting/settings/custom-fields/reorder`, {
        method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({codes})
      });
      await loadCustomFields();
    });
    card.addEventListener('dragover', event => {
      event.preventDefault();
      if (dragged && dragged !== card) {
        const box = card.getBoundingClientRect();
        card.parentNode.insertBefore(dragged, event.clientY < box.top + box.height / 2 ? card : card.nextSibling);
      }
    });
  });
}

function renderInspectorCustomFields(inv) {
  const container = document.getElementById('inspector-custom-fields');
  const fields = STATE.customFields.filter(field => field.visible_in_analysis);
  if (!fields.length) { container.innerHTML = ''; return; }
  container.innerHTML = `<hr class="divider"><div class="section-title" style="font-size:.85rem;">Trường tùy chỉnh</div><div class="field-row">${fields.map(field => {
    const value = (inv.ext.customFields || {})[field.code];
    const type = field.field_type === 'number' ? 'number' : 'text';
    return `<div class="field-group"><label class="field-label">${escapeHtml(field.name)}${field.is_required ? ' *' : ''}</label><input class="field-input custom-field-input" data-code="${escapeHtml(field.code)}" type="${type}" value="${escapeHtml(value ?? '')}" ${field.is_required ? 'required' : ''}></div>`;
  }).join('')}</div>`;
}

// ── Inspector modal (XSS Protected) ────────────────────
function openInspector(id) {
  const inv = STATE.invoices.find(i => i.id === id);
  if (!inv) return;
  STATE.inspecting = inv;
  const e = inv.ext;
  if (!STATE.customFields.length) loadCustomFields();

  setText('insp-filename', inv.file);
  setVal('f-supplier', e.supplier); setVal('f-tax-id', e.tax);
  setVal('f-inv-num', e.num);       setVal('f-inv-date', e.date);
  setVal('f-currency', e.currency); setVal('f-subtotal', e.sub);
  setVal('f-vat', e.vat);           setVal('f-total', e.total);
  // Invoice type & note
  const typeSelect = document.getElementById('f-invoice-type');
  if (typeSelect) typeSelect.value = inv.invoice_type || 'dau_vao';
  const noteInput = document.getElementById('f-note');
  if (noteInput) noteInput.value = inv.note || '';
  renderInspectorCustomFields(inv);

  const wb = document.getElementById('insp-warn-box');
  if (inv.warnings && inv.warnings.length) {
    wb.style.display = 'block';
    wb.innerHTML = '⚠️ ' + inv.warnings.map(w => escapeHtml(w)).join('<br>');
  } else { wb.style.display = 'none'; }

  const ll = document.getElementById('line-items-list');
  ll.innerHTML = '';
  const items = normalizeLineItems(e.items);
  if (items.length === 0) {
    addLineItemRow({ desc: `Cung cấp dịch vụ / Hàng hóa theo ${inv.file}`, qty: 1, price: e.sub || 0, amt: e.sub || 0 });
  } else {
    items.forEach(it => addLineItemRow(it));
  }

  const dp = document.getElementById('doc-paper-content');
  const rawFileUrl = `${API_BASE}/api/v1/accounting/files/${inv.id}`;
  const isPdf = inv.file.toLowerCase().endsWith('.pdf');
  const isImg = /\.(png|jpg|jpeg|tiff|webp)$/i.test(inv.file);

  if (isPdf) {
    dp.innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
        <span style="font-weight:600; font-size:.85rem; color:var(--t-1);">📄 File Chứng Từ PDF Gốc</span>
        <a href="${rawFileUrl}" target="_blank" class="btn btn-ghost btn-sm" style="font-size:.73rem; text-decoration:none;">↗️ Mở cửa sổ mới</a>
      </div>
      <iframe src="${rawFileUrl}" style="width:100%; height:550px; border:1px solid var(--c-surface-2); border-radius:8px; background:#ffffff;"></iframe>
    `;
  } else if (isImg) {
    dp.innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
        <span style="font-weight:600; font-size:.85rem; color:var(--t-1);">🖼️ Ảnh Chứng Từ Gốc</span>
        <a href="${rawFileUrl}" target="_blank" class="btn btn-ghost btn-sm" style="font-size:.73rem; text-decoration:none;">↗️ Mở cửa sổ mới</a>
      </div>
      <div style="text-align:center; background:var(--c-surface-2); padding:10px; border-radius:8px;">
        <img src="${rawFileUrl}" style="max-width:100%; max-height:550px; object-fit:contain; border-radius:6px;" alt="${escapeHtml(inv.file)}">
      </div>
    `;
  } else {
    dp.innerHTML = `
      <div style="text-align:right; margin-bottom:8px;">
        <a href="${rawFileUrl}" target="_blank" class="btn btn-ghost btn-sm" style="font-size:.73rem; text-decoration:none;">📄 Tải/Xem file gốc</a>
      </div>
      <h4 style="margin-bottom:6px; text-transform:uppercase;">${escapeHtml(e.supplier)}</h4>
      <p style="font-size:.72rem; color:var(--t-3); margin-bottom:12px;">Mã số thuế: <span class="hl">${escapeHtml(e.tax) || 'Chưa có'}</span></p>
      <div style="display:flex; justify-content:space-between; margin-bottom:12px; font-size:.75rem;">
        <div><strong>HÓA ĐƠN GTGT</strong><br>Số: <span class="hl">${escapeHtml(e.num)}</span></div>
        <div style="text-align:right;">Ngày: <span class="hl">${escapeHtml(e.date)}</span><br>Đơn vị tiền: ${escapeHtml(e.currency)}</div>
      </div>
      <table class="doc-table">
        <thead><tr><th>Tên hàng hóa/DV</th><th>SL</th><th>Đơn giá</th><th>Thành tiền</th></tr></thead>
        <tbody>
          ${items.map(it => `<tr><td>${escapeHtml(it.desc || it.description)}</td><td style="text-align:center">${escapeHtml(it.qty || it.quantity)}</td><td style="text-align:right">${fmtMoney(it.price || it.unit_price, e.currency)}</td><td style="text-align:right"><span class="hl">${fmtMoney(it.amt || it.amount, e.currency)}</span></td></tr>`).join('')}
        </tbody>
      </table>
      <div style="text-align:right; font-size:.8rem; line-height:2; margin-top:10px;">
        Tiền hàng: ${fmtMoney(e.sub, e.currency)}<br>
        Thuế VAT: ${fmtMoney(e.vat, e.currency)}<br>
        <strong>Tổng thanh toán: <span class="hl" style="font-size:.9rem;">${fmtMoney(e.total, e.currency)}</span></strong>
      </div>
    `;
  }

  document.getElementById('inspector-modal').classList.add('open');
}

function closeInspector() {
  document.getElementById('inspector-modal').classList.remove('open');
  STATE.inspecting = null;
}

async function saveInspector() {
  const inv = STATE.inspecting;
  if (!inv) return;

  const lineRows = document.querySelectorAll('#line-items-list .line-item-row');
  const newItems = [];
  lineRows.forEach(r => {
    const desc = r.querySelector('.item-desc').value.trim();
    const qty  = parseFloat(r.querySelector('.item-qty').value) || 1;
    const price = parseFloat(r.querySelector('.item-price').value) || 0;
    const amt  = parseFloat(r.querySelector('.item-amt').value) || (qty * price);
    if (desc || amt > 0) {
      newItems.push({ description: desc || 'Hàng hóa / Dịch vụ', quantity: qty, unit_price: price, amount: amt });
    }
  });

  const nextExt = {
    supplier: getVal('f-supplier'),
    tax: getVal('f-tax-id'),
    num: getVal('f-inv-num'),
    date: getVal('f-inv-date'),
    currency: getVal('f-currency'),
    sub: parseFloat(getVal('f-subtotal')) || 0,
    vat: parseFloat(getVal('f-vat')) || 0,
    total: parseFloat(getVal('f-total')) || 0,
    items: newItems,
    customFields: {}
  };
  const newInvoiceType = (document.getElementById('f-invoice-type') || {}).value || inv.invoice_type || 'dau_vao';
  const newNote = (document.getElementById('f-note') || {}).value || '';
  document.querySelectorAll('.custom-field-input').forEach(input => {
    nextExt.customFields[input.dataset.code] = input.type === 'number'
      ? (parseFloat(input.value) || 0) : input.value;
  });

  const ok = await window.StateSync.updateInvoiceStatus(
    inv.id,
    'approved',
    { ext: nextExt, status: 'approved', invoice_type: newInvoiceType, note: newNote },
    () => updateInvoiceOnBackend(inv.batch_id, inv.id, {
      supplier_name: nextExt.supplier,
      supplier_tax_id: nextExt.tax,
      invoice_number: nextExt.num,
      invoice_date: nextExt.date,
      currency: nextExt.currency,
      subtotal: nextExt.sub,
      tax_amount: nextExt.vat,
      total_amount: nextExt.total,
      items: nextExt.items,
      custom_fields: nextExt.customFields,
      invoice_type: newInvoiceType,
      note: newNote,
      status: 'approved'
    })
  );

  if (ok) {
    inv.invoice_type = newInvoiceType;
    inv.note = newNote;
    closeInspector();
    recalcStats();
    renderTable();
  }
}

function selectAiProvider(provider, silent) {
  localStorage.setItem('AI_PROVIDER', provider);
  updateAiEngineCards(provider);
  updateSidebarAiBadge(provider);
  if (!silent) {
    const status = document.getElementById('cfg-key-status');
    if (status) {
      status.textContent = `⚡ Đã chuyển sang sử dụng ${provider === 'openai' ? 'OpenAI GPT-4o (ChatGPT)' : 'Google Gemini'}.`;
      setTimeout(() => { if (status.textContent.startsWith('⚡')) status.textContent = ''; }, 3000);
    }
  }
}

function updateAiEngineCards(activeProvider) {
  const geminiCard = document.getElementById('engine-card-gemini');
  const geminiDot  = document.getElementById('engine-dot-gemini');
  const geminiStat = document.getElementById('engine-status-gemini');

  const openaiCard = document.getElementById('engine-card-openai');
  const openaiDot  = document.getElementById('engine-dot-openai');
  const openaiStat = document.getElementById('engine-status-openai');

  if (activeProvider === 'openai') {
    if (openaiCard) { openaiCard.style.borderColor = 'var(--c-brand)'; openaiCard.style.opacity = '1'; }
    if (openaiDot)  openaiDot.textContent = '🟢';
    if (openaiStat) openaiStat.textContent = 'Đang dùng';

    if (geminiCard) { geminiCard.style.borderColor = 'var(--c-border)'; geminiCard.style.opacity = '.7'; }
    if (geminiDot)  geminiDot.textContent = '⚪';
    if (geminiStat) geminiStat.textContent = 'Không hoạt động';
  } else {
    if (geminiCard) { geminiCard.style.borderColor = 'var(--c-brand)'; geminiCard.style.opacity = '1'; }
    if (geminiDot)  geminiDot.textContent = '🟢';
    if (geminiStat) geminiStat.textContent = 'Đang dùng';

    if (openaiCard) { openaiCard.style.borderColor = 'var(--c-border)'; openaiCard.style.opacity = '.7'; }
    if (openaiDot)  openaiDot.textContent = '⚪';
    if (openaiStat) openaiStat.textContent = 'Không hoạt động';
  }
}

function updateSidebarAiBadge(provider) {
  const footerSpan = document.querySelector('.sidebar-footer span');
  if (footerSpan) {
    footerSpan.textContent = provider === 'openai'
      ? 'OpenAI GPT-4o · Sẵn sàng'
      : 'Gemini Flash · Sẵn sàng';
  }
}

function saveAiKeys() {
  const gInput = document.getElementById('cfg-gemini-key');
  const oInput = document.getElementById('cfg-openai-key');
  const status = document.getElementById('cfg-key-status');

  const gKey = gInput ? gInput.value.trim() : '';
  const oKey = oInput ? oInput.value.trim() : '';

  if (gKey) localStorage.setItem('GEMINI_API_KEY', gKey);
  else localStorage.removeItem('GEMINI_API_KEY');

  if (oKey) localStorage.setItem('OPENAI_API_KEY', oKey);
  else localStorage.removeItem('OPENAI_API_KEY');

  if (status) {
    status.textContent = '✅ Đã lưu cấu hình AI Key thành công!';
    setTimeout(() => { status.textContent = ''; }, 4000);
  }
}

function saveGeminiKey() {
  saveAiKeys();
}

function setVal(id, v) { const el = document.getElementById(id); if (el) el.value = v ?? ''; }
function getVal(id)    { const el = document.getElementById(id); return el ? el.value : ''; }

// ── Export REAL XLSX ───────────────────────────────────
function exportExcel() {
  const approved = STATE.invoices.filter(i => i.status === 'approved');
  if (!approved.length) {
    alert('Chưa có hóa đơn nào được Duyệt để xuất Excel!\n\nHãy duyệt ít nhất 1 hóa đơn trước khi xuất.');
    return;
  }

  const colLabels = getColumnLabels();
  const colLabelsParam = Object.keys(colLabels).length
    ? `&column_labels=${encodeURIComponent(JSON.stringify(colLabels))}`
    : '';

  const downloadUrl = `${API_BASE}/api/v1/accounting/export-all.xlsx?t=${Date.now()}${colLabelsParam}`;

  const a = document.createElement('a');
  a.href = downloadUrl;
  a.download = `Bao_Cao_Hoa_Don_${new Date().toISOString().slice(0,10)}.xlsx`;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => { if (a.parentNode) a.parentNode.removeChild(a); }, 200);
}

// ── Column Labels for Excel Export ─────────────────────
const COLUMN_KEYS = [
  { key: 'file_name',        label: 'Tên File Gốc' },
  { key: 'invoice_type',     label: 'Loại HĐ' },
  { key: 'invoice_number',   label: 'Số Hóa Đơn' },
  { key: 'invoice_date',     label: 'Ngày HĐ' },
  { key: 'supplier_name',    label: 'Nhà Cung Cấp' },
  { key: 'supplier_tax_id',  label: 'Mã Số Thuế' },
  { key: 'currency',         label: 'Loại Tiền' },
  { key: 'subtotal',         label: 'Tiền Hàng' },
  { key: 'tax_amount',       label: 'Tiền Thuế VAT' },
  { key: 'total_amount',     label: 'Tổng Thanh Toán' },
  { key: 'note',             label: 'Ghi Chú' },
];

const PRESETS = {
  'misa': {
    invoice_number: 'Số chứng từ',
    invoice_date:   'Ngày chứng từ',
    supplier_name:  'Tên đối tượng',
    supplier_tax_id:'Mã số thuế',
    subtotal:       'Doanh thu/Chi phí',
    tax_amount:     'Thuế GTGT',
    total_amount:   'Tổng tiền',
    note:           'Diễn giải',
    file_name:      'Tên file',
    invoice_type:   'Loại chứng từ',
    currency:       'Đơn vị tiền',
  },
  'fast': {
    invoice_number: 'Số HĐ',
    invoice_date:   'Ngày HĐ',
    supplier_name:  'Tên nhà cung cấp',
    supplier_tax_id:'MST',
    subtotal:       'Tiền hàng',
    tax_amount:     'Thuế',
    total_amount:   'Tổng cộng',
    note:           'Ghi chú',
    file_name:      'File',
    invoice_type:   'Phân loại',
    currency:       'Tiền tệ',
  },
  'general': {},  // Reset to defaults
};

function getColumnLabels() {
  try {
    return JSON.parse(localStorage.getItem('XLSX_COLUMN_LABELS') || '{}');
  } catch { return {}; }
}

function saveColumnLabels() {
  const labels = {};
  COLUMN_KEYS.forEach(({ key }) => {
    const el = document.getElementById(`col-label-${key}`);
    if (el && el.value.trim()) labels[key] = el.value.trim();
  });
  localStorage.setItem('XLSX_COLUMN_LABELS', JSON.stringify(labels));
  const s = document.getElementById('col-label-status');
  if (s) { s.textContent = '✅ Đã lưu!'; setTimeout(() => { s.textContent = ''; }, 2500); }
}

function applyColumnPreset(presetKey) {
  const preset = PRESETS[presetKey] || {};
  COLUMN_KEYS.forEach(({ key, label }) => {
    const el = document.getElementById(`col-label-${key}`);
    if (el) el.value = preset[key] || label;
  });
  // Auto-save immediately
  saveColumnLabels();
  const s = document.getElementById('col-label-status');
  const names = { misa: 'MISA', fast: 'Fast Accounting', general: 'Mặc định' };
  if (s) { s.textContent = `✅ Đã áp dụng mẫu ${names[presetKey] || presetKey}!`; setTimeout(() => { s.textContent = ''; }, 2500); }
}

function renderColumnLabelSettings() {
  const el = document.getElementById('col-labels-list');
  if (!el) return;
  const saved = getColumnLabels();
  el.innerHTML = COLUMN_KEYS.map(({ key, label }) => `
    <div class="field-group" style="min-width:180px;">
      <label class="field-label" style="font-size:.72rem; color:var(--t-3);">${escapeHtml(label)}</label>
      <input class="field-input" id="col-label-${escapeHtml(key)}"
        value="${escapeHtml(saved[key] || label)}"
        placeholder="${escapeHtml(label)}" style="font-size:.8rem; padding:7px 10px;">
    </div>
  `).join('');
}


// ── Search modal ───────────────────────────────────────
let searchFocusIdx = -1;

function openSearch() {
  document.getElementById('search-modal').classList.add('open');
  setTimeout(() => {
    const inp = document.getElementById('search-input');
    if (inp) { inp.value = ''; inp.focus(); }
  }, 50);
  renderSearchResults('');
}

function closeSearch() {
  document.getElementById('search-modal').classList.remove('open');
  searchFocusIdx = -1;
}

function renderSearchResults(q) {
  const filtered = q
    ? APPS.filter(a => (a.title + a.desc).toLowerCase().includes(q.toLowerCase()))
    : APPS;

  const container = document.getElementById('modal-results');
  if (!filtered.length) {
    container.innerHTML = `<div style="padding:20px; text-align:center; color:var(--t-3);">Không tìm thấy kết quả.</div>`;
    return;
  }

  container.innerHTML = filtered.map((a, idx) => `
    <div class="modal-result-item${idx === searchFocusIdx ? ' focused' : ''}" onclick="switchView('${escapeHtml(a.id)}')">
      <span class="mri-icon">${escapeHtml(a.icon)}</span>
      <div>
        <div class="mri-title">${escapeHtml(a.title)}</div>
        <div class="mri-sub">${escapeHtml(a.desc)}</div>
      </div>
    </div>
  `).join('');
}

// ── Keyboard shortcuts ─────────────────────────────────
document.addEventListener('keydown', e => {
  if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
    e.preventDefault();
    openSearch();
  }
  if (e.key === 'Escape') {
    closeSearch();
    closeInspector();
  }
});

// ── Init ───────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', () => {
      if (item.classList.contains('disabled')) return;
      switchView(item.getAttribute('data-view'));
    });
  });

  document.querySelectorAll('.fpill').forEach(pill => {
    pill.addEventListener('click', () => {
      document.querySelectorAll('.fpill').forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
      STATE.filter = pill.getAttribute('data-f');
      renderTable();
    });
  });

  const searchEl = document.getElementById('t-search');
  if (searchEl) searchEl.addEventListener('input', e => { STATE.query = e.target.value; renderTable(); });

  document.getElementById('search-trigger')?.addEventListener('click', openSearch);
  document.getElementById('search-modal')?.addEventListener('click', e => {
    if (e.target === document.getElementById('search-modal')) closeSearch();
  });

  const searchInput = document.getElementById('search-input');
  if (searchInput) {
    searchInput.addEventListener('input', e => renderSearchResults(e.target.value));
    searchInput.addEventListener('keydown', e => {
      const items = document.querySelectorAll('.modal-result-item');
      if (e.key === 'ArrowDown') { searchFocusIdx = Math.min(searchFocusIdx + 1, items.length - 1); renderSearchResults(searchInput.value); }
      if (e.key === 'ArrowUp')   { searchFocusIdx = Math.max(searchFocusIdx - 1, 0); renderSearchResults(searchInput.value); }
      if (e.key === 'Enter' && searchFocusIdx >= 0) items[searchFocusIdx]?.click();
    });
  }

  const fileInput = document.createElement('input');
  fileInput.type = 'file';
  fileInput.multiple = true;
  fileInput.accept = '.pdf,.png,.jpg,.jpeg,.tiff';
  fileInput.id = 'file-input-hidden';
  fileInput.style.display = 'none';
  document.body.appendChild(fileInput);

  fileInput.addEventListener('change', e => {
    if (e.target.files && e.target.files.length) {
      uploadRealFiles(e.target.files);
    }
  });

  const dz = document.getElementById('drop-zone');
  if (dz) {
    dz.addEventListener('dragover', e => { e.preventDefault(); dz.classList.add('over'); });
    dz.addEventListener('dragleave', () => dz.classList.remove('over'));
    dz.addEventListener('drop', e => {
      e.preventDefault();
      dz.classList.remove('over');
      if (e.dataTransfer.files && e.dataTransfer.files.length) {
        uploadRealFiles(e.dataTransfer.files);
      }
    });
  }

  document.getElementById('btn-upload')?.addEventListener('click', () => {
    fileInput.click();
  });

  loadBatchesFromBackend();
  loadCustomFields();
  updateSidebarAiBadge(localStorage.getItem('AI_PROVIDER') || 'gemini');
  updateThemeButton(localStorage.getItem('aiws-theme') || 'light');
});
