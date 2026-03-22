  // ========== TAB SWITCHING ==========
  function switchTab(tab) {
    const chatElements = [document.getElementById('messages'), document.getElementById('input-area')];
    const ebPanel = document.getElementById('exercise-bank');
    const tabChat = document.getElementById('tab-chat');
    const tabExercises = document.getElementById('tab-exercises');

    if (tab === 'exercises') {
      chatElements.forEach(el => el.style.display = 'none');
      ebPanel.classList.add('visible');
      tabChat.classList.remove('active');
      tabExercises.classList.add('active');
      loadExerciseBank();
    } else {
      chatElements.forEach(el => el.style.display = '');
      ebPanel.classList.remove('visible');
      tabChat.classList.add('active');
      tabExercises.classList.remove('active');
    }
  }

  async function loadExerciseBank() {
    // Show skeleton while loading
    const container = document.getElementById('exercise-bank');
    if (container && !container.querySelector('.eb-header')) {
      container.innerHTML = `<div style="padding:24px;display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px">
        ${Array(6).fill('<div class="skeleton skeleton-card"></div>').join('')}
      </div>`;
    }
    try {
      const res = await apiFetch('/api/questions');
      const questions = await res.json();
      window._lastQuestions = questions;
      renderExerciseBank(questions);
    } catch (e) {
      console.error('Failed to load exercise bank', e);
    }
  }

  // ========== SIDEBAR ==========
  function toggleSidebar() {
    document.getElementById('sidebar').classList.toggle('open');
    document.getElementById('overlay').classList.toggle('active');
  }

  function closeSidebar() {
    document.getElementById('sidebar').classList.remove('open');
    document.getElementById('overlay').classList.remove('active');
  }

  // ========== LIGHTBOX ==========
  function openLightbox(src) {
    document.getElementById('lightbox-img').src = src;
    document.getElementById('lightbox-overlay').classList.add('active');
  }

  function downloadLightboxImg() {
    const src = document.getElementById('lightbox-img').src;
    const a = document.createElement('a');
    a.href = src;
    a.download = 'circuit-diagram.png';
    a.click();
  }

  // ESC closes lightbox and modals
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      document.getElementById('lightbox-overlay').classList.remove('active');
      closeDeleteModal();
      closeExamPicker();
    }
  });

  // ========== DELETE MODAL ==========
  let pendingDeleteConvId = null;

  function showDeleteModal(convId) {
    pendingDeleteConvId = convId;
    document.getElementById('delete-modal').classList.add('active');
    document.getElementById('confirm-delete-btn').onclick = confirmDeleteConv;
  }

  function closeDeleteModal() {
    document.getElementById('delete-modal').classList.remove('active');
    pendingDeleteConvId = null;
  }

  async function confirmDeleteConv() {
    if (!pendingDeleteConvId) return;
    const convId = pendingDeleteConvId;
    closeDeleteModal();
    try {
      await apiFetch(`/api/conversations/${convId}`, { method: 'DELETE' });
      if (currentConvId === convId) {
        currentConvId = null;
        showWelcome();
      }
      loadConversations();
    } catch (err) {
      showToast('שגיאה במחיקה', 'error');
    }
  }

  // ========== SIDEBAR SEARCH ==========
  function filterConversations(query) {
    const items = document.querySelectorAll('.conv-item');
    const groups = document.querySelectorAll('.conv-date-group');
    const q = query.trim().toLowerCase();
    if (!q) {
      items.forEach(el => el.style.display = '');
      groups.forEach(el => el.style.display = '');
      return;
    }
    items.forEach(el => {
      const title = el.querySelector('.conv-title')?.textContent.toLowerCase() || '';
      el.style.display = title.includes(q) ? '' : 'none';
    });
    // Hide empty groups
    groups.forEach(g => {
      let next = g.nextElementSibling;
      let hasVisible = false;
      while (next && !next.classList.contains('conv-date-group')) {
        if (next.style.display !== 'none') hasVisible = true;
        next = next.nextElementSibling;
      }
      g.style.display = hasVisible ? '' : 'none';
    });
  }

  // ========== RENDERING ==========
  function renderMarkdown(text) {
    // Protect math blocks from marked.js processing
    const mathBlocks = [];
    // Extract $$...$$ display blocks first
    let protected_text = text.replace(/\$\$([\s\S]*?)\$\$/g, (match) => {
      mathBlocks.push(match);
      return `%%MATH_BLOCK_${mathBlocks.length - 1}%%`;
    });
    // Extract \[...\] display blocks
    protected_text = protected_text.replace(/\\\[([\s\S]*?)\\\]/g, (match) => {
      mathBlocks.push(match);
      return `%%MATH_BLOCK_${mathBlocks.length - 1}%%`;
    });
    // Extract $...$ inline blocks (not preceded/followed by $)
    protected_text = protected_text.replace(/(?<!\$)\$(?!\$)((?:[^$]|\n)*?)\$(?!\$)/g, (match) => {
      mathBlocks.push(match);
      return `%%MATH_BLOCK_${mathBlocks.length - 1}%%`;
    });
    // Extract \(...\) inline blocks
    protected_text = protected_text.replace(/\\\(([\s\S]*?)\\\)/g, (match) => {
      mathBlocks.push(match);
      return `%%MATH_BLOCK_${mathBlocks.length - 1}%%`;
    });

    const renderer = new marked.Renderer();
    const originalCode = renderer.code.bind(renderer);
    renderer.code = function({text, lang, escaped}) {
      // Handle both modern '{text, lang}' signature and legacy '(code, lang)' signature
      const codeArg = text !== undefined ? text : arguments[0];
      const langArg = lang !== undefined ? lang : arguments[1];
      const escapedArg = escaped !== undefined ? escaped : arguments[2];
      
      const rendered = typeof originalCode === 'function' && originalCode.length === 1 
          ? originalCode({text: codeArg, lang: langArg, escaped: escapedArg}) 
          : originalCode(codeArg, langArg, escapedArg);
          
      if (!langArg || langArg.toLowerCase().includes('python') || langArg.toLowerCase().includes('bash')) {
        const title = langArg ? `הרצת קוד (${langArg})` : 'פלט מערכת (Console)';
        return `<details class="reasoning-block"><summary>${title}</summary><div class="reasoning-content">${rendered}</div></details>`;
      }
      return rendered;
    };
    
    marked.setOptions({ breaks: true, gfm: true, renderer: renderer });
    let html = marked.parse(protected_text);

    // Restore math blocks — escape HTML special chars so browser doesn't
    // misinterpret < > & inside LaTeX (e.g. $a < b$, \begin{aligned} a &= b)
    html = html.replace(/%%MATH_BLOCK_(\d+)%%/g, (_, idx) => {
      const block = mathBlocks[parseInt(idx)] || '';
      return block
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
    });

    return html;
  }

  function renderMath(element) {
    if (typeof renderMathInElement !== 'undefined') {
      renderMathInElement(element, {
        delimiters: [
          { left: '$$', right: '$$', display: true },
          { left: '$', right: '$', display: false },
          { left: '\\[', right: '\\]', display: true },
          { left: '\\(', right: '\\)', display: false }
        ],
        throwOnError: false
      });
    }
  }

  function escapeHtml(str) {
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function escapeAttr(str) {
    // Escape for use inside HTML attribute values (double-quoted)
    return (str || '')
      .replace(/&/g, '&amp;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  // ========== SCROLL-TO-BOTTOM BUTTON ==========
  document.getElementById('messages').addEventListener('scroll', function() {
    const el = this;
    const distFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    const btn = document.getElementById('scroll-bottom-btn');
    if (btn) {
      btn.classList.toggle('visible', distFromBottom > 200);
    }
  });

  // ========== TOAST NOTIFICATIONS ==========
  function showToast(message, type = 'info', duration = 3000) {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `<span>${message}</span>`;
    container.appendChild(toast);
    setTimeout(() => {
      toast.classList.add('removing');
      setTimeout(() => toast.remove(), 300);
    }, duration);
  }