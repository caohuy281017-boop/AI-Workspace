'use strict';

(function initFreeTools() {
  const catalog = window.AIWorkspaceToolCatalog;
  const engine = window.AIWorkspaceToolFunctions;
  if (!catalog) throw new Error('Không tải được danh mục công cụ.');
  if (!engine) throw new Error('Không tải được bộ xử lý công cụ.');

  const behaviors = {
    'word-count': { transform: engine.countText, primaryAction: 'Thống kê độ dài' },
    'clean-text': { transform: engine.cleanText, primaryAction: 'Làm sạch văn bản' },
    'case-converter': { actions: caseActions },
    'remove-accents': { transform: engine.removeVietnameseAccents, primaryAction: 'Bỏ dấu tiếng Việt' },
    'html-to-text': { transform: engine.htmlToText, primaryAction: 'Lấy nội dung chữ' },
    'markdown-to-text': { transform: engine.markdownToText, primaryAction: 'Lấy văn bản thuần' },
    'remove-duplicate-lines': { transform: engine.uniqueLines, primaryAction: 'Xóa dòng trùng' },
    'sort-lines': { actions: sortActions },
    'reverse-lines': { transform: engine.reverseLines, primaryAction: 'Đảo thứ tự' },
    'remove-empty-lines': { transform: engine.removeEmptyLines, primaryAction: 'Xóa dòng trống' },
    'number-lines': { transform: engine.numberLines, primaryAction: 'Đánh số danh sách' },
    'join-split-lines': { actions: joinSplitActions },
    'text-workflow': { actions: textWorkflowActions },
    'json-format': { transform: engine.formatJson, primaryAction: 'Kiểm tra & trình bày' },
    'json-minify': { transform: engine.minifyJson, primaryAction: 'Thu gọn JSON' },
    'csv-to-json': { transform: engine.csvToJson, primaryAction: 'Chuyển sang JSON' },
    'extract-contacts': { actions: contactActions },
    'slug': { transform: engine.toSlug, primaryAction: 'Tạo đường dẫn' },
    'url-encode': { actions: urlActions },
    'base64': { actions: base64Actions },
  };
  const tools = catalog.tools.map(tool => ({ ...tool, ...behaviors[tool.id] }));
  const groups = catalog.groups;
  const favoriteStorageKey = 'aiws-favorite-tools';
  let activeGroup = 'all';
  let favoriteIds = loadFavoriteIds();
  const byId = id => document.getElementById(id);

  function loadFavoriteIds() {
    try {
      const saved = JSON.parse(localStorage.getItem(favoriteStorageKey) || '[]');
      return new Set(Array.isArray(saved) ? saved : []);
    } catch (_err) {
      return new Set();
    }
  }

  function saveFavoriteIds() {
    try { localStorage.setItem(favoriteStorageKey, JSON.stringify([...favoriteIds])); } catch (_err) { /* Storage can be disabled. */ }
  }

  function caseActions(text) { return [ ['CHỮ HOA', () => engine.convertCase(text, 'upper')], ['chữ thường', () => engine.convertCase(text, 'lower')], ['Kiểu Tiêu Đề', () => engine.convertCase(text, 'title')], ['Kiểu câu', () => engine.convertCase(text, 'sentence')] ]; }
  function sortActions(text) { return [ ['A → Z', () => engine.sortLines(text, 'asc')], ['Z → A', () => engine.sortLines(text, 'desc')], ['Ngắn → dài', () => engine.sortLines(text, 'length-asc')], ['Dài → ngắn', () => engine.sortLines(text, 'length-desc')] ]; }
  function urlActions(text) { return [ ['Mã hóa', () => engine.transformUrl(text, 'encode')], ['Giải mã', () => engine.transformUrl(text, 'decode')] ]; }
  function base64Actions(text) { return [ ['Mã hóa', () => engine.transformBase64(text, 'encode')], ['Giải mã', () => engine.transformBase64(text, 'decode')] ]; }
  function joinSplitActions(text) { return [ ['Nối bằng dấu phẩy', () => engine.joinLines(text, ', ')], ['Nối bằng dấu chấm phẩy', () => engine.joinLines(text, '; ')], ['Tách theo dấu phẩy', () => engine.splitCommaSeparated(text)] ]; }
  function contactActions(text) { return [
    ['Lấy email', () => engine.extractContacts(text, 'email')],
    ['Lấy số điện thoại', () => engine.extractContacts(text, 'phone')],
    ['Lấy URL', () => engine.extractContacts(text, 'url')],
  ]; }
  function textWorkflowActions(text) { return [
    ['Làm sạch', () => engine.runTextWorkflow(text, 'clean')],
    ['Làm sạch + xóa trùng', () => engine.runTextWorkflow(text, 'dedupe')],
    ['Chuẩn hóa + A→Z', () => engine.runTextWorkflow(text, 'sort')],
    ['Chuẩn hóa slug từng dòng', () => engine.runTextWorkflow(text, 'slug')],
  ]; }

  function renderFilters() {
    const host=byId('tools-filters'); if(!host) return;
    host.innerHTML='';
    [{ id:'all', title:'Tất cả công cụ' }, ...groups].forEach(group => {
      const count = group.id === 'all' ? tools.length : tools.filter(tool => tool.group === group.id).length;
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'tools-filter' + (group.id === activeGroup ? ' active' : '');
      button.innerHTML = `<span></span><small>${count}</small>`;
      button.querySelector('span').textContent = group.title;
      button.onclick = () => { activeGroup=group.id; renderFilters(); renderTools(); };
      host.appendChild(button);
    });
  }

  function createToolCard(tool) {
    const card = document.createElement('article');
    card.className = 'tool-card';
    card.dataset.group = tool.group;
    card.innerHTML = `<button type="button" class="tool-favorite" aria-pressed="false"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="m12 3 2.75 5.57 6.15.9-4.45 4.33 1.05 6.12L12 17.03l-5.5 2.89 1.05-6.12L3.1 9.47l6.15-.9L12 3Z"/></svg></button><button type="button" class="tool-card-main"><span class="tool-icon"></span><span class="tool-card-title"></span><span class="tool-card-description"></span><span class="tool-card-example"><strong>Ví dụ</strong><span></span></span><span class="tool-card-open">Mở công cụ <span aria-hidden="true">→</span></span></button>`;
    card.querySelector('.tool-icon').textContent = tool.icon;
    card.querySelector('.tool-card-title').textContent = tool.title;
    card.querySelector('.tool-card-description').textContent = tool.description;
    card.querySelector('.tool-card-example span').textContent = tool.example;
    card.querySelector('.tool-card-main').onclick = () => openTool(tool);

    const favorite = card.querySelector('.tool-favorite');
    const syncFavorite = () => {
      const isFavorite = favoriteIds.has(tool.id);
      favorite.classList.toggle('active', isFavorite);
      favorite.setAttribute('aria-pressed', String(isFavorite));
      favorite.setAttribute('aria-label', isFavorite ? `Bỏ ${tool.title} khỏi yêu thích` : `Thêm ${tool.title} vào yêu thích`);
    };
    favorite.onclick = () => {
      favoriteIds.has(tool.id) ? favoriteIds.delete(tool.id) : favoriteIds.add(tool.id);
      saveFavoriteIds();
      renderTools();
    };
    syncFavorite();
    return card;
  }

  function appendToolSection(host, group, sectionTools, options = {}) {
    if (!sectionTools.length) return;
    const section = document.createElement('section');
    section.className = 'tool-group';
    section.innerHTML = `<div class="tool-group-head"><div><span class="tool-group-kicker"></span><h2></h2><p></p></div><span class="tool-group-count"></span></div><div class="tools-grid"></div>`;
    section.querySelector('.tool-group-kicker').textContent = options.kicker || 'NHÓM CÔNG CỤ';
    section.querySelector('h2').textContent = options.title || group.title;
    section.querySelector('p').textContent = options.description || group.description;
    section.querySelector('.tool-group-count').textContent = `${sectionTools.length} công cụ`;
    const cards = section.querySelector('.tools-grid');
    sectionTools.forEach(tool => cards.appendChild(createToolCard(tool)));
    host.appendChild(section);
  }

  function renderTools() {
    const host=byId('tools-grid'); if(!host) return;
    const q=(byId('tools-search')?.value||'').trim().toLocaleLowerCase('vi');
    const toolsInGroup = tools.filter(tool => activeGroup === 'all' || tool.group === activeGroup);
    const visible = q ? catalog.rankTools(toolsInGroup, q) : toolsInGroup;
    host.innerHTML='';

    if (q) {
      appendToolSection(host, groups[0], visible, {
        kicker: 'KẾT QUẢ TÌM KIẾM',
        title: visible.length ? `Công cụ phù hợp với “${q}”` : 'Không tìm thấy công cụ',
        description: visible.length ? 'Chọn công cụ có ví dụ gần nhất với việc bạn đang cần xử lý.' : 'Thử tìm bằng công việc như “xóa trùng”, “lấy email”, “đổi chữ” hoặc “JSON”.',
      });
    } else if (activeGroup === 'all') {
      const favoriteTools = tools.filter(tool => favoriteIds.has(tool.id));
      appendToolSection(host, groups[0], favoriteTools, {
        kicker: 'TRUY CẬP NHANH',
        title: 'Công cụ yêu thích của bạn',
        description: 'Các công cụ bạn đã đánh dấu sao để sử dụng lại nhanh hơn.',
      });
      groups.forEach(group => appendToolSection(host, group, tools.filter(tool => tool.group === group.id)));
    } else {
      const group = groups.find(item => item.id === activeGroup);
      if (group) appendToolSection(host, group, visible);
    }
    if(byId('tools-empty')) byId('tools-empty').hidden=visible.length>0;
  }
  function openTool(tool) {
    const maxLocalFileBytes = 5 * 1024 * 1024;
    const maxDocumentFileBytes = 20 * 1024 * 1024;
    const localPattern = /\.(txt|csv|json|html|md|xml|log|tsv)$/i;
    const documentPattern = /\.(doc|docx|docm|pdf|rtf|odt|ods|odp|ppt|pps|pot|pptx|pptm|ppsx|ppsm|xls|xlsx|xlsm|xlsb|epub)$/i;
    const triggerCard = document.activeElement;
    const dialog = document.createElement('dialog');
    dialog.className = 'tool-dialog';
    const dialogTitleId = `tool-dialog-title-${tool.id}`;
    const inputId = `tool-input-${tool.id}`;
    const outputId = `tool-output-${tool.id}`;
    dialog.setAttribute('aria-labelledby', dialogTitleId);
    dialog.innerHTML = `<div class="tool-dialog-head"><h2 id="${dialogTitleId}"><span class="tool-icon"></span><span class="dialog-title"></span></h2><button class="tool-dialog-close" type="button" aria-label="Đóng">✕</button></div><div class="tool-dialog-body"><section class="tool-dialog-intro"><span class="tool-dialog-eyebrow"></span><p class="dialog-description"></p><div class="tool-dialog-use"><strong>Dùng khi</strong><span class="dialog-use-when"></span></div><div class="tool-dialog-example"><strong>Ví dụ trước → sau</strong><span class="dialog-example-value"></span></div></section><div class="tool-editor-grid"><div class="tool-editor"><div class="tool-editor-header"><label class="tool-input-label" for="${inputId}"></label><div class="tool-file-meta"><span class="tool-filename" aria-live="polite"></span><button class="tool-file-btn" type="button"><svg xmlns="http://www.w3.org/2000/svg" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>Tải tài liệu</button></div></div><div class="tool-file-help">Có thể dán nội dung hoặc tải TXT/CSV/JSON, Word, PDF, PowerPoint, Excel · tối đa 20 MB</div><div class="tool-file-error" role="alert" aria-live="assertive"></div><textarea id="${inputId}" class="tool-input"></textarea><div class="tool-char-count"><span class="char-num">0</span> ký tự</div></div><div class="tool-editor"><div class="tool-editor-header"><label class="tool-output-label" for="${outputId}"></label></div><textarea id="${outputId}" class="tool-output" readonly></textarea><div class="tool-char-count"><span class="out-char-num">0</span> ký tự</div><div class="sr-only tool-result-status" aria-live="polite"></div></div></div><div class="tool-actions"></div></div>`;

    dialog.querySelector('.tool-icon').textContent = tool.icon;
    dialog.querySelector('.dialog-title').textContent = tool.title;
    dialog.querySelector('.tool-dialog-eyebrow').textContent = groups.find(group => group.id === tool.group)?.title || 'Công cụ miễn phí';
    dialog.querySelector('.dialog-description').textContent = tool.description;
    dialog.querySelector('.dialog-use-when').textContent = tool.useWhen;
    dialog.querySelector('.dialog-example-value').textContent = tool.example;
    dialog.querySelector('.tool-input-label').textContent = tool.inputLabel;
    dialog.querySelector('.tool-output-label').textContent = tool.outputLabel;
    const input = dialog.querySelector('.tool-input');
    const output = dialog.querySelector('.tool-output');
    input.placeholder = tool.placeholder;
    output.placeholder = `${tool.outputLabel} sẽ xuất hiện ở đây sau khi xử lý`;
    const actions = dialog.querySelector('.tool-actions');
    const charNum = dialog.querySelector('.char-num');
    const outCharNum = dialog.querySelector('.out-char-num');
    const filename = dialog.querySelector('.tool-filename');
    const fileError = dialog.querySelector('.tool-file-error');
    const fileButton = dialog.querySelector('.tool-file-btn');
    const resultStatus = dialog.querySelector('.tool-result-status');

    const showFileError = message => {
      fileError.textContent = message;
      fileError.classList.toggle('visible', Boolean(message));
    };
    const setInputFromFile = (content, name) => {
      input.value = content;
      input.dispatchEvent(new Event('input'));
      filename.textContent = name;
      filename.classList.add('visible');
      showFileError('');
    };
    input.addEventListener('input', () => {
      charNum.textContent = input.value.length.toLocaleString('vi');
    });

    const run = fn => {
      try {
        const result = String(fn(input.value));
        output.value = result;
        outCharNum.textContent = result.length.toLocaleString('vi');
        resultStatus.textContent = `Đã xử lý xong, kết quả có ${result.length} ký tự`;
      } catch (err) {
        output.value = 'Lỗi: ' + err.message;
        outCharNum.textContent = output.value.length.toLocaleString('vi');
        resultStatus.textContent = 'Xử lý thất bại: ' + err.message;
      }
    };

    const actionDefs = tool.actions ? tool.actions(input.value) : [[tool.primaryAction || 'Tạo kết quả', () => tool.transform(input.value)]];
    actionDefs.forEach(([label]) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'tool-action primary';
      button.textContent = label;
      button.onclick = () => {
        const defs = tool.actions ? tool.actions(input.value) : [[tool.primaryAction || 'Tạo kết quả', () => tool.transform(input.value)]];
        const match = defs.find(item => item[0] === label);
        if (match) run(match[1]);
      };
      actions.appendChild(button);
    });

    const copy = document.createElement('button');
    copy.type = 'button';
    copy.className = 'tool-action';
    copy.textContent = 'Sao chép kết quả';
    copy.onclick = async () => {
      if (!output.value) return;
      try {
        await navigator.clipboard.writeText(output.value);
      } catch (_err) {
        output.select();
        document.execCommand('copy');
        input.focus();
      }
      copy.textContent = 'Đã sao chép ✓';
      setTimeout(() => copy.textContent = 'Sao chép kết quả', 1200);
    };
    actions.appendChild(copy);

    const clear = document.createElement('button');
    clear.type = 'button';
    clear.className = 'tool-action';
    clear.textContent = 'Xóa';
    clear.onclick = () => {
      input.value = '';
      output.value = '';
      charNum.textContent = '0';
      outCharNum.textContent = '0';
      filename.textContent = '';
      filename.classList.remove('visible');
      showFileError('');
      input.focus();
    };
    actions.appendChild(clear);

    const hint = document.createElement('span');
    hint.className = 'tool-shortcut-hint';
    hint.textContent = 'Ctrl+Enter / Cmd+Enter';
    actions.appendChild(hint);

    fileButton.onclick = () => {
      const picker = document.createElement('input');
      picker.type = 'file';
      picker.accept = '.txt,.csv,.json,.html,.md,.xml,.log,.tsv,.doc,.docx,.docm,.pdf,.rtf,.odt,.ods,.odp,.ppt,.pps,.pot,.pptx,.pptm,.ppsx,.ppsm,.xls,.xlsx,.xlsm,.xlsb,.epub';
      picker.onchange = async () => {
        const file = picker.files?.[0];
        if (!file) return;
        showFileError('');

        if (localPattern.test(file.name)) {
          if (file.size > maxLocalFileBytes) {
            showFileError(`File ${file.name} quá lớn. File text được giới hạn 5 MB.`);
            return;
          }
          const reader = new FileReader();
          reader.onerror = () => showFileError('Không đọc được file. Hãy thử lưu lại dưới dạng UTF-8.');
          reader.onload = () => setInputFromFile(String(reader.result || ''), file.name);
          reader.readAsText(file, 'UTF-8');
          return;
        }

        if (!documentPattern.test(file.name)) {
          showFileError('Định dạng này chưa được hỗ trợ. Hãy chọn file văn bản, Word, PDF, PowerPoint hoặc Excel.');
          return;
        }
        if (file.size > maxDocumentFileBytes) {
          showFileError(`File ${file.name} quá lớn. Tài liệu được giới hạn 20 MB.`);
          return;
        }

        const originalButton = fileButton.innerHTML;
        fileButton.disabled = true;
        fileButton.classList.add('busy');
        fileButton.textContent = 'Đang trích xuất...';
        try {
          const formData = new FormData();
          formData.append('file', file);
          const response = await fetch(`${window.location.origin}/api/v1/tools/extract-text`, {
            method: 'POST',
            body: formData,
          });
          const payload = await response.json().catch(() => ({}));
          if (!response.ok) throw new Error(payload.detail || `Không thể đọc tài liệu (${response.status})`);
          const extracted = tool.id === 'markdown-to-text'
            ? String(payload.content || '')
            : engine.markdownToText(String(payload.content || ''));
          setInputFromFile(extracted, file.name);
        } catch (err) {
          showFileError(err.message || 'Không thể trích xuất nội dung tài liệu.');
        } finally {
          fileButton.disabled = false;
          fileButton.classList.remove('busy');
          fileButton.innerHTML = originalButton;
        }
      };
      picker.click();
    };

    input.addEventListener('keydown', e => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        e.preventDefault();
        actions.querySelector('.primary')?.click();
      }
    });
    dialog.querySelector('.tool-dialog-close').onclick = () => dialog.close();
    dialog.addEventListener('close', () => {
      dialog.remove();
      if (triggerCard?.classList?.contains('tool-card-main')) triggerCard.focus();
    });
    document.body.appendChild(dialog);
    dialog.showModal();
    input.focus();
  }

  document.addEventListener('DOMContentLoaded',()=>{ renderFilters(); renderTools(); byId('tools-search')?.addEventListener('input',renderTools); });
})();
