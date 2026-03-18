// ========== STATE ==========
  let currentConvId = null;
  let isLoading = false;
  let pendingImage = null;  // { base64: string, mimeType: string, dataUrl: string, name: string }

  // ========== AUTH FETCH HELPER ==========
  function apiFetch(url, options = {}) {
    const token = localStorage.getItem('authToken');
    const headers = { ...(options.headers || {}) };
    if (token) headers['Authorization'] = 'Bearer ' + token;
    return fetch(url, { ...options, headers }).then(res => {
      if (res.status === 401) {
        localStorage.removeItem('authToken');
        showLoginScreen();
      }
      return res;
    });
  }

  // ========== INIT ==========
  // ========== AUTH: LOGIN ==========
  function showLoginScreen() {
    document.getElementById('login-overlay').style.display = 'flex';
  }

  function hideLoginScreen() {
    document.getElementById('login-overlay').style.display = 'none';
  }

  async function doLogin() {
    const em = document.getElementById('login-email').value;
    const pw = document.getElementById('login-password').value;
    const errEl = document.getElementById('login-error');
    errEl.textContent = '';
    if (!em || !pw) { errEl.textContent = 'נא להזין אימייל וסיסמה'; return; }
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: em, password: pw })
      });
      if (!res.ok) {
        errEl.textContent = 'סיסמה שגויה';
        return;
      }
      const { token } = await res.json();
      localStorage.setItem('authToken', token);
      hideLoginScreen();
      loadConversations();
    } catch (e) {
      errEl.textContent = 'שגיאת חיבור';
    }
  }

  async function doLogout() {
    await apiFetch('/api/auth/logout', { method: 'POST' }).catch(() => {});
    localStorage.removeItem('authToken');
    showLoginScreen();
  }

  document.addEventListener('DOMContentLoaded', () => {
    const token = localStorage.getItem('authToken');
    if (!token) {
      showLoginScreen();
    } else {
      hideLoginScreen();
      showWelcome();
      loadConversations();
      document.getElementById('user-input').focus();
    }
  });

  document.addEventListener('keydown', (e) => {
    const overlay = document.getElementById('login-overlay');
    if (overlay && overlay.style.display !== 'none' && e.key === 'Enter') {
      doLogin();
    }
  });

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

  // ========== TOPIC COLOR SYSTEM ==========
  // Keywords matched with .includes() — order matters (first match wins)
  const TOPIC_RULES = [
    // מכונות חשמל
    { keys: ['שנאי','שנאים','Transformer','transformer','Parallel Transformer','העמסת שנאים'], cfg: { icon: '🔌', color: '#a855f7', label: 'שנאים' } },
    { keys: ['אסינכרוני','השראה','Induction','induction'], cfg: { icon: '⚙️', color: '#22c55e', label: 'מנוע אסינכרוני' } },
    { keys: ['סינכרוני','Synchronous','synchronous'], cfg: { icon: '🔄', color: '#f59e0b', label: 'סינכרוני' } },
    { keys: ['DC','dc','מנוע DC','גנרטור DC'], cfg: { icon: '🔋', color: '#ef4444', label: 'DC' } },
    { keys: ['הינע','הנעה חשמלית','VFD','vfd','וסת מהירות','Chopper','chopper','Drive','drive'], cfg: { icon: '🏭', color: '#3b82f6', label: 'הנעה חשמלית' } },
    // מערכות הספק
    { keys: ['שיפור מקדם הספק','מקדם הספק','Power Factor','power factor','קבלים','קבל'], cfg: { icon: '📊', color: '#06b6d4', label: 'שיפור מקדם הספק' } },
    { keys: ['תאורה','תאורת פנים','תאורת חוץ','גוף תאורה','נורה','Lighting'], cfg: { icon: '💡', color: '#fbbf24', label: 'תאורה' } },
    { keys: ['רשת חלוקה','רשת רדיאלית','רשת טבעתית','רדיאלי','טבעתית','מינימום חומר'], cfg: { icon: '🔗', color: '#14b8a6', label: 'רשת חלוקה' } },
    { keys: ['נקודת האפס','נקודת אפס','מוליך אפס','זינה צפה'], cfg: { icon: '⚫', color: '#64748b', label: 'נקודת האפס' } },
    { keys: ['העמסה','עומס שנאי'], cfg: { icon: '⚖️', color: '#8b5cf6', label: 'העמסת שנאים' } },
    // מתקני חשמל
    { keys: ['הגנה מפני חשמול','חשמול','הארקה','הארקות','TN','TT','IT','RCD','מפסק פחת'], cfg: { icon: '🛡️', color: '#ec4899', label: 'הגנה והארקות' } },
    { keys: ['כבל','כבלים','מוליך','חתך','הגנה','Cable','cable','Protection','מפסק','נתיך'], cfg: { icon: '🔒', color: '#f97316', label: 'כבלים והגנה' } },
  ];
  const DEFAULT_TOPIC = { icon: '📋', color: '#6b7280', label: 'כללי' };

  function getTopicConfig(topic) {
    for (const rule of TOPIC_RULES) {
      for (const key of rule.keys) {
        if (topic.includes(key)) return rule.cfg;
      }
    }
    return DEFAULT_TOPIC;
  }

  // Store questions globally for filtering
  let _allQuestions = [];
  let _activeFilter = 'all';
  let _activeDifficulty = 0; // 0=all, 1=easy, 2=medium, 3=hard
  let _activeSolvedFilter = 'all'; // 'all' | 'solved' | 'unsolved'

  function hasSolution(q) {
    return !!(q.solution && q.solution.trim() && q.solution.trim() !== 'לא פתור');
  }

  function renderExerciseBank(questions) {
    _allQuestions = questions;
    _activeFilter = 'all';
    document.getElementById('eb-search').value = '';
    renderFilterBar(questions);
    renderStats(questions);
    renderCards(questions);
  }

  function renderStats(questions) {
    const statsEl = document.getElementById('eb-stats');
    if (!questions.length) { statsEl.innerHTML = ''; return; }
    const topics = new Set(questions.map(q => getTopicConfig(q.topic || 'כללי').label));
    const withSolution = questions.filter(hasSolution).length;
    const solvedPct = Math.round(withSolution / questions.length * 100);

    const dCounts = { 1: 0, 2: 0, 3: 0 };
    questions.forEach(q => { if (q.difficulty) dCounts[q.difficulty]++; });

    statsEl.innerHTML = `
      <div><span>${questions.length}</span> שאלות &nbsp;|&nbsp; <span>${topics.size}</span> נושאים &nbsp;|&nbsp; <span style="color:#4ade80">${withSolution}</span> פתורות (${solvedPct}%)</div>
      <div class="eb-diff-filters">
        <button class="eb-diff-pill ${_activeSolvedFilter==='all'?'active':''}" onclick="setSolvedFilter('all')">📋 הכל</button>
        <button class="eb-diff-pill ${_activeSolvedFilter==='solved'?'solved-active':''}" onclick="setSolvedFilter('solved')">✅ פתורות (${withSolution})</button>
        <button class="eb-diff-pill ${_activeSolvedFilter==='unsolved'?'unsolved-active':''}" onclick="setSolvedFilter('unsolved')">📝 ללא פתרון (${questions.length - withSolution})</button>
        &nbsp;
        <button class="eb-diff-pill ${_activeDifficulty===0?'active':''}" onclick="setDifficulty(0)">רמה: הכל</button>
        <button class="eb-diff-pill ${_activeDifficulty===1?'active':''}" onclick="setDifficulty(1)">🟢 קל (${dCounts[1]})</button>
        <button class="eb-diff-pill ${_activeDifficulty===2?'active':''}" onclick="setDifficulty(2)">🟡 בינוני (${dCounts[2]})</button>
        <button class="eb-diff-pill ${_activeDifficulty===3?'active':''}" onclick="setDifficulty(3)">🔴 קשה (${dCounts[3]})</button>
      </div>
    `;
  }

  function setSolvedFilter(val) {
    _activeSolvedFilter = val;
    filterExercises();
    renderStats(_allQuestions);
  }

  function setDifficulty(d) {
    _activeDifficulty = d;
    filterExercises();
    renderStats(_allQuestions);
  }

  function renderFilterBar(questions) {
    const bar = document.getElementById('eb-filter-bar');
    if (!questions.length) { bar.innerHTML = ''; return; }

    // Count per normalized topic
    const counts = {};
    questions.forEach(q => {
      const cfg = getTopicConfig(q.topic || 'כללי');
      counts[cfg.label] = (counts[cfg.label] || 0) + 1;
    });

    // Build unique topics preserving order
    const seen = new Set();
    const topicList = [];
    questions.forEach(q => {
      const cfg = getTopicConfig(q.topic || 'כללי');
      if (!seen.has(cfg.label)) {
        seen.add(cfg.label);
        topicList.push(cfg);
      }
    });

    let html = `<button class="eb-filter-chip active" style="background:var(--accent)" onclick="setFilter('all')">הכל <span class="chip-count">${questions.length}</span></button>`;
    topicList.forEach(cfg => {
      html += `<button class="eb-filter-chip" data-topic="${cfg.label}" onclick="setFilter('${cfg.label}')" style="--chip-color:${cfg.color}">
        ${cfg.icon} ${cfg.label} <span class="chip-count">${counts[cfg.label]}</span>
      </button>`;
    });
    bar.innerHTML = html;
  }

  function setFilter(topic) {
    _activeFilter = topic;
    // Update active chip
    document.querySelectorAll('.eb-filter-chip').forEach(chip => {
      chip.classList.remove('active');
      chip.style.background = '';
      chip.style.borderColor = '';
      chip.style.color = '';
    });
    if (topic === 'all') {
      const allChip = document.querySelector('.eb-filter-chip');
      allChip.classList.add('active');
      allChip.style.background = 'var(--accent)';
    } else {
      document.querySelectorAll('.eb-filter-chip[data-topic]').forEach(chip => {
        if (chip.dataset.topic === topic) {
          chip.classList.add('active');
          const cfg = TOPIC_RULES.map(r=>r.cfg).find(c=>c.label===topic) || DEFAULT_TOPIC;
          chip.style.background = cfg.color;
          chip.style.borderColor = cfg.color;
          chip.style.color = 'white';
        }
      });
    }
    filterExercises();
  }

  function filterExercises() {
    const search = (document.getElementById('eb-search').value || '').trim().toLowerCase();
    let filtered = _allQuestions;
    if (_activeFilter !== 'all') {
      filtered = filtered.filter(q => getTopicConfig(q.topic || 'כללי').label === _activeFilter);
    }
    if (_activeDifficulty > 0) {
      filtered = filtered.filter(q => q.difficulty === _activeDifficulty);
    }
    if (_activeSolvedFilter === 'solved') {
      filtered = filtered.filter(hasSolution);
    } else if (_activeSolvedFilter === 'unsolved') {
      filtered = filtered.filter(q => !hasSolution(q));
    }
    if (search) {
      filtered = filtered.filter(q => (q.text || '').toLowerCase().includes(search) || (q.topic || '').toLowerCase().includes(search));
    }
    renderCards(filtered);
  }

  function renderCards(questions) {
    const container = document.getElementById('eb-content');

    if (!questions.length) {
      const isFiltered = _activeFilter !== 'all' || (document.getElementById('eb-search').value || '').trim();
      container.innerHTML = `
        <div class="eb-empty">
          <div class="eb-empty-icon">${isFiltered ? '🔍' : '📚'}</div>
          <p>${isFiltered ? 'לא נמצאו שאלות מתאימות.' : 'אין תרגילים עדיין.<br>העלה תמונה של דף תרגילים או מבחן והבוט יחלץ את השאלות אוטומטית.'}</p>
          ${isFiltered ? '' : '<button class="eb-upload-btn" onclick="document.getElementById(\'eb-upload-input\').click()">📎 העלה תמונה</button>'}
        </div>`;
      return;
    }

    // Group by normalized topic
    const groups = {};
    questions.forEach(q => {
      const cfg = getTopicConfig(q.topic || 'כללי');
      const key = cfg.label;
      if (!groups[key]) groups[key] = { cfg, items: [] };
      groups[key].items.push(q);
    });

    container.innerHTML = Object.entries(groups).map(([topic, { cfg, items }]) => `
      <div class="eb-topic-section" data-topic="${cfg.label}"
           ondragover="event.preventDefault(); this.classList.add('drag-target')"
           ondragleave="this.classList.remove('drag-target')"
           ondrop="dropOnTopic(event, this)">
        <div class="eb-topic-title" onclick="this.parentElement.classList.toggle('collapsed')" style="border-bottom-color:${cfg.color};color:${cfg.color}">
          ${cfg.icon} ${escapeHtml(topic)}
          <span class="count" style="background:${cfg.color}">${items.length}</span>
        </div>
        <div class="eb-cards">
          ${items.map(q => {
            const qCfg = getTopicConfig(q.topic || 'כללי');
            const diffLabel = q.difficulty === 3 ? '🔴 קשה' : q.difficulty === 2 ? '🟡 בינוני' : q.difficulty === 1 ? '🟢 קל' : '';
            const diffClass = q.difficulty ? `eb-diff eb-diff-${q.difficulty}` : '';
            return `
            <div class="eb-card ${hasSolution(q) ? 'is-solved' : ''}" data-qid="${q.id}" draggable="true"
                 ondragstart="dragCard(event, ${q.id})"
                 ondragend="this.classList.remove('dragging')"
                 style="border-right-color:${qCfg.color}" onmouseenter="this.style.boxShadow='0 0 16px ${qCfg.color}22'" onmouseleave="this.style.boxShadow=''">
              <div class="eb-card-badges">
                <span class="eb-badge eb-badge-topic" style="background:${qCfg.color}">${qCfg.icon} ${escapeHtml(q.topic || 'כללי')}</span>
                <span class="eb-status-badge ${hasSolution(q) ? 'eb-status-solved' : 'eb-status-unsolved'}">${hasSolution(q) ? '✅ פתור' : '📝 שאלה'}</span>
                ${diffLabel ? `<span class="${diffClass}">${diffLabel}</span>` : ''}
                ${q.source ? `<span class="eb-badge eb-badge-source">${escapeHtml(q.source)}</span>` : ''}
              </div>
              ${q.image_url ? `<img class="eb-card-img" src="${q.image_url}" onclick="openLightbox('${q.image_url}')" alt="תמונת שאלה" />` : ''}
              <div class="eb-card-text">${escapeHtml(q.text)}</div>
              <div class="eb-card-actions">
                <button class="eb-guide-btn" onclick="solveExercise('${encodeURIComponent(q.text)}', '${q.image_url || ''}', true)">🎯 פתור בהנחיה</button>
                ${q.solution
                  ? `<button class="eb-solve-btn" style="background:rgba(34,197,94,0.15);border-color:rgba(34,197,94,0.3);color:#4ade80" onclick="toggleEbSolution(this.parentElement.nextElementSibling)">📖 הצג פתרון</button>`
                  : `<button class="eb-solve-btn" onclick="solveExercise('${encodeURIComponent(q.text)}', '${q.image_url || ''}')">⚡ פתור בצ'אט</button>`
                }
                <button class="eb-edit-btn" onclick="openEditModal(${q.id})">✏️ ערוך</button>
                <button class="eb-delete-btn" onclick="deleteExerciseAndRefresh(${q.id})">✕ מחק</button>
              </div>
              ${q.solution ? `
              <div class="eb-solution-wrap" data-qid="${q.id}">${q.solution}</div>
              ` : ''}
            </div>`;
          }).join('')}
        </div>
      </div>
    `).join('');
  }

  async function solveExercise(encodedText, imageUrl, guided = false) {
    const rawText = decodeURIComponent(encodedText);
    const text = guided
      ? 'הנחה אותי לפתור את השאלה הבאה שלב אחר שלב. אל תיתן את הפתרון המלא בבת אחת — שאל שאלות מנחות ותחכה לתגובות שלי.\n\nשאלה:\n' + rawText
      : rawText;
    switchTab('chat');
    newChat();

    // If exercise has an image (circuit diagram), attach it
    if (imageUrl) {
      try {
        const resp = await fetch(imageUrl);
        const blob = await resp.blob();
        const reader = new FileReader();
        reader.onload = (e) => {
          const dataUrl = e.target.result;
          const [header, base64] = dataUrl.split(',');
          const mimeType = header.match(/:(.*?);/)[1];
          pendingImage = { base64, mimeType, dataUrl, name: 'circuit-diagram.png' };
          document.getElementById('image-preview').src = dataUrl;
          document.getElementById('image-preview-name').textContent = 'סרטוט מעגל';
          document.getElementById('image-preview-wrap').classList.add('visible');
          document.getElementById('attach-btn').classList.add('has-image');
          document.getElementById('user-input').value = text;
          autoResize(document.getElementById('user-input'));
          sendMessage();
        };
        reader.readAsDataURL(blob);
      } catch {
        // Fallback: send without image
        document.getElementById('user-input').value = text;
        autoResize(document.getElementById('user-input'));
        sendMessage();
      }
    } else {
      document.getElementById('user-input').value = text;
      document.getElementById('user-input').focus();
      autoResize(document.getElementById('user-input'));
      sendMessage();
    }
  }

  async function deleteExerciseAndRefresh(id) {
    await apiFetch(`/api/questions/${id}`, { method: 'DELETE' });
    loadExerciseBank();
    loadQBank();
  }

  async function batchProcessQuestions() {
    const btn = document.getElementById('eb-batch-btn');
    const oldText = btn.textContent;
    btn.disabled = true;

    // Step 1: Deduplicate
    btn.textContent = '🧹 מנקה כפילויות...';
    try {
      const dedupRes = await apiFetch('/api/questions/deduplicate', { method: 'POST' });
      const dedupData = await dedupRes.json();
      if (dedupData.removed > 0) {
        showToast(`🧹 הוסרו ${dedupData.removed} כפילויות. נשארו ${dedupData.remaining} שאלות.`, 'success');
        loadExerciseBank();
      }
    } catch (e) {
      showToast('שגיאה בניקוי: ' + e.message, 'error');
    }

    // Step 2: Batch solve via SSE stream
    btn.textContent = '🧠 מתחיל לפתור...';
    try {
      const response = await apiFetch('/api/questions/batch-solve', { method: 'POST' });
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split('\n');
        buffer = lines.pop();

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const data = JSON.parse(line.slice(6));
            if (data.status === 'solving') {
              btn.textContent = `🧠 פותר ${data.current}/${data.total}...`;
            } else if (data.status === 'progress' && data.current % 5 === 0) {
              loadExerciseBank();
            } else if (data.done) {
              if (data.solved > 0) {
                showToast(`🧠 נפתרו ${data.solved} שאלות! סה״כ ${data.total} במאגר.`, 'success');
              } else {
                showToast(data.message || 'הכל כבר פתור!', 'info');
              }
            }
          } catch {}
        }
      }
      loadExerciseBank();
      loadQBank();
    } catch (e) {
      showToast('שגיאה בפתרון: ' + e.message, 'error');
    } finally {
      btn.disabled = false;
      btn.textContent = oldText;
    }
  }

  function toggleEbSolution(el) {
    // el can be a button (with nextElementSibling being the wrap) or the wrap itself
    const wrap = el.classList.contains('eb-solution-wrap') ? el : el.nextElementSibling;
    if (!wrap || !wrap.classList.contains('eb-solution-wrap')) return;

    const isOpen = wrap.classList.toggle('open');

    // Find the toggle button in the card to update its text
    const card = wrap.closest('.eb-card');
    const btn = card?.querySelector('.eb-solve-btn, .eb-solution-toggle');
    if (btn) {
      btn.textContent = isOpen ? '📖 הסתר פתרון' : '📖 הצג פתרון';
    }

    // Render markdown + math on first open
    if (isOpen && !wrap.dataset.rendered) {
      wrap.innerHTML = renderMarkdown(wrap.textContent);
      renderMath(wrap);
      wrap.dataset.rendered = '1';
    }
  }

  // ---- Edit Modal ----
  let _editQid = null;

  function openEditModal(qid) {
    const questions = window._lastQuestions || [];
    const q = questions.find(x => x.id === qid);
    if (!q) return;
    _editQid = qid;

    const topics = ['שנאים','מנוע אסינכרוני','גנרטור סינכרוני','מנוע סינכרוני','מנוע DC','גנרטור DC','הנעה חשמלית','כללי'];
    const topicOptions = topics.map(t =>
      `<option value="${t}" ${t === q.topic ? 'selected' : ''}>${t}</option>`
    ).join('');

    const overlay = document.createElement('div');
    overlay.className = 'eb-edit-overlay';
    overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };
    overlay.innerHTML = `
      <div class="eb-edit-modal">
        <h3>✏️ עריכת תרגיל #${qid}</h3>
        <label>נושא</label>
        <select id="edit-topic">${topicOptions}</select>
        <label>טקסט השאלה</label>
        <textarea id="edit-text" rows="5" dir="auto">${escapeHtml(q.text)}</textarea>
        <label>פתרון</label>
        <textarea id="edit-solution" rows="8" dir="auto">${escapeHtml(q.solution || '')}</textarea>
        <div class="eb-edit-actions">
          <button class="eb-edit-save" onclick="saveEditModal()">💾 שמור</button>
          <button class="eb-edit-cancel" onclick="this.closest('.eb-edit-overlay').remove()">ביטול</button>
        </div>
      </div>
    `;
    document.body.appendChild(overlay);
  }

  async function saveEditModal() {
    if (!_editQid) return;
    const overlay = document.querySelector('.eb-edit-overlay');
    const btn = overlay.querySelector('.eb-edit-save');
    btn.disabled = true;
    btn.textContent = '⏳ שומר...';

    const updates = {
      topic: document.getElementById('edit-topic').value,
      text: document.getElementById('edit-text').value.trim(),
      solution: document.getElementById('edit-solution').value.trim(),
    };

    try {
      const res = await apiFetch(`/api/questions/${_editQid}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates)
      });
      if (!res.ok) throw new Error('Server error');
      overlay.remove();
      showToast('✅ התרגיל עודכן');
      await loadExerciseBank();
    } catch (e) {
      btn.textContent = '❌ שגיאה';
      setTimeout(() => { btn.disabled = false; btn.textContent = '💾 שמור'; }, 2000);
    }
  }

  // ---- Save chat answer to bank ----
  async function saveChatToBank(btn) {
    const bubble = btn.closest('.bubble');
    const solution = bubble.innerText.replace(/📋 העתק|📄 פתרון נכון|💾 שמור לבנק|✓ נשמר!/g, '').trim();

    // Find the user message before this bot message
    const msgEl = bubble.closest('.message');
    const allMsgs = Array.from(document.querySelectorAll('#messages .message'));
    const idx = allMsgs.indexOf(msgEl);
    let userText = '';
    for (let i = idx - 1; i >= 0; i--) {
      if (allMsgs[i].classList.contains('user')) {
        userText = allMsgs[i].querySelector('.bubble')?.innerText?.trim() || '';
        break;
      }
    }

    if (!userText || !solution) {
      showToast('❌ לא נמצא טקסט שאלה או פתרון');
      return;
    }

    btn.disabled = true;
    btn.textContent = '⏳ שומר...';

    try {
      const res = await apiFetch('/api/questions/save-from-chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: userText, solution })
      });
      const data = await res.json();
      btn.textContent = '✓ נשמר!';
      btn.classList.add('saved');
      showToast(`✅ ${data.message || 'נשמר לבנק'}`);
    } catch (e) {
      btn.textContent = '❌ שגיאה';
      setTimeout(() => { btn.disabled = false; btn.textContent = '💾 שמור לבנק'; }, 2000);
    }
  }

  // ---- Drag & Drop ----
  let _draggedQid = null;

  function dragCard(event, qid) {
    _draggedQid = qid;
    event.target.classList.add('dragging');
    event.dataTransfer.effectAllowed = 'move';
  }

  async function dropOnTopic(event, section) {
    event.preventDefault();
    section.classList.remove('drag-target');
    if (!_draggedQid) return;

    // Get the topic label from the section's data attribute
    const topicLabel = section.dataset.topic;
    if (!topicLabel) return;

    // Map label back to the actual topic name
    const rule = TOPIC_RULES.find(r => r.cfg.label === topicLabel);
    const topicName = rule ? rule.keys[0] : topicLabel;

    try {
      await apiFetch(`/api/questions/${_draggedQid}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic: topicName })
      });
      showToast(`✅ הועבר ל-${topicLabel}`);
      await loadExerciseBank();
    } catch (e) {
      showToast('❌ שגיאה בהעברה');
    }
    _draggedQid = null;
  }

  async function ebUploadImage(event) {
    const file = event.target.files[0];
    if (!file) return;

    // Show loading state
    const btn = document.getElementById('eb-upload-btn-main');
    const oldText = btn ? btn.textContent : '📎 חלץ מתמונה';
    if (btn) {
      btn.disabled = true;
      btn.textContent = '⏳ מחלץ, מתייג ופותר... (עד 3 דקות)';
    }

    const reader = new FileReader();
    reader.onload = async (e) => {
      const dataUrl = e.target.result;
      const [header, base64] = dataUrl.split(',');
      const mimeType = header.match(/:(.*?);/)[1];
      try {
        const res = await apiFetch('/api/questions/extract-image', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: file.name, image_data: base64, image_mime_type: mimeType })
        });
        const data = await res.json();
        const saved = data.saved || 0;
        const dupes = data.duplicates || 0;
        const solved = data.solved || 0;
        const extracted = data.extracted || 0;

        loadExerciseBank();
        loadQBank();

        if (saved > 0) {
          showToast(`✅ חילוץ מתמונה הושלם! ${saved} שאלות נשמרו, ${solved} נפתרו אוטומטית.${dupes ? ` (${dupes} כפילויות דולגו)` : ''}`, 'success');
        } else if (dupes > 0) {
          showToast(`כל ${dupes} השאלות כבר קיימות במאגר.`, 'info');
        } else if (extracted === 0) {
          showToast('לא נמצאו תרגילים בתמונה', 'info');
        } else {
          showToast('לא נמצאו שאלות חדשות.', 'info');
        }
      } catch (e) {
        showToast('שגיאה: ' + e.message, 'error');
      } finally {
        if (btn) {
          btn.disabled = false;
          btn.textContent = oldText;
        }
      }
    };
    reader.readAsDataURL(file);
    event.target.value = '';
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

  // ========== CONVERSATIONS ==========
  async function loadConversations() {
    // Show skeleton while loading
    const listEl = document.getElementById('conversations-list');
    if (listEl && !listEl.querySelector('.conv-item')) {
      listEl.innerHTML = Array(4).fill('<div class="skeleton skeleton-conv"></div>').join('');
    }
    try {
      const res = await apiFetch('/api/conversations');
      if (!res.ok) throw new Error('Network response was not ok');
      const convs = await res.json();
      if (!Array.isArray(convs)) throw new Error('Expected array');
      renderConversations(convs);
    } catch (e) {
      console.error('Failed to load conversations', e);
      listEl.innerHTML =
        '<div style="padding:12px;color:#ef4444;font-size:13px;text-align:center">שגיאה בטעינת היסטוריה</div>';
    }
  }

  function getConvIcon(title) {
    const t = (title || '').toLowerCase();
    if (t.includes('שנאי') || t.includes('transformer')) return '🔌';
    if (t.includes('אסינכרוני') || t.includes('השראה') || t.includes('induction')) return '⚙️';
    if (t.includes('סינכרוני') || t.includes('synchronous')) return '🔄';
    if (t.includes('dc') || t.includes('DC')) return '🔋';
    if (t.includes('הינע') || t.includes('vfd') || t.includes('chopper')) return '🏭';
    if (t.includes('כבל') || t.includes('הגנה') || t.includes('העמס')) return '🛡️';
    if (t.includes('מקדם') || t.includes('הספק')) return '⚡';
    if (t.includes('תמונה') || t.includes('image')) return '🖼️';
    return '💬';
  }

  function getDateGroup(dateStr) {
    if (!dateStr) return 'ישן';
    const d = new Date(dateStr);
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const yesterday = new Date(today); yesterday.setDate(today.getDate() - 1);
    const weekAgo = new Date(today); weekAgo.setDate(today.getDate() - 7);

    if (d >= today) return 'היום';
    if (d >= yesterday) return 'אתמול';
    if (d >= weekAgo) return 'השבוע';
    return 'ישן יותר';
  }

  function formatTime(dateStr) {
    if (!dateStr) return '';
    const d = new Date(dateStr);
    return d.toLocaleTimeString('he-IL', { hour: '2-digit', minute: '2-digit' });
  }

  function renderConversations(convs) {
    const list = document.getElementById('conversations-list');
    list.innerHTML = '';

    if (convs.length === 0) {
      list.innerHTML = '<div style="padding:12px;color:var(--text-muted);font-size:13px;text-align:center">אין שיחות עדיין</div>';
      return;
    }

    // Group by date
    const groups = {};
    const groupOrder = ['היום', 'אתמול', 'השבוע', 'ישן יותר'];
    convs.forEach(conv => {
      const group = getDateGroup(conv.updated_at);
      if (!groups[group]) groups[group] = [];
      groups[group].push(conv);
    });

    groupOrder.forEach(groupName => {
      const items = groups[groupName];
      if (!items || !items.length) return;

      const header = document.createElement('div');
      header.className = 'conv-date-group';
      header.textContent = groupName;
      list.appendChild(header);

      items.forEach(conv => {
        const item = document.createElement('div');
        item.className = 'conv-item' + (conv.id === currentConvId ? ' active' : '');
        item.dataset.id = conv.id;
        const icon = getConvIcon(conv.title);
        const time = formatTime(conv.updated_at);
        item.innerHTML = `
          <span class="conv-icon">${icon}</span>
          <div class="conv-info">
            <div class="conv-title" title="${escapeHtml(conv.title)}">${escapeHtml(conv.title)}</div>
            <div class="conv-time">${time}</div>
          </div>
          <button class="conv-delete" onclick="deleteConv(event, '${conv.id}')" title="מחק">✕</button>
        `;
        item.addEventListener('click', () => loadConversation(conv.id));
        list.appendChild(item);
      });
    });
  }

  async function loadConversation(convId) {
    currentConvId = convId;
    closeSidebar();

    // Highlight active
    document.querySelectorAll('.conv-item').forEach(el => {
      el.classList.toggle('active', el.dataset.id === convId);
    });

    // Clear messages
    const messagesEl = document.getElementById('messages');
    messagesEl.innerHTML = '';

    try {
      const res = await apiFetch(`/api/conversations/${convId}/messages`);
      const msgs = await res.json();

      if (msgs.length === 0) {
        showWelcome();
        return;
      }

      msgs.forEach(msg => {
        const role = msg.role === 'user' ? 'user' : 'bot';
        appendMessage(role, msg.content);
      });

      scrollToBottom();
    } catch (e) {
      console.error('Failed to load messages', e);
    }
  }

  async function deleteConv(e, convId) {
    e.preventDefault();
    e.stopPropagation();
    showDeleteModal(convId);
    return;
    // Legacy code below not reached
    try {
      await apiFetch(`/api/conversations/${convId}`, { method: 'DELETE' });

      if (currentConvId === convId) {
        currentConvId = null;
        showWelcome();
      }

      loadConversations();
    } catch (err) {
      console.error('Failed to delete conversation:', err);
      showToast('תקלה במחיקת השיחה: ' + err.message, 'error');
    }
  }

  function newChat() {
    currentConvId = null;
    showWelcome();
    closeSidebar();
    document.querySelectorAll('.conv-item').forEach(el => el.classList.remove('active'));
    document.getElementById('user-input').focus();
  }

  function showWelcome() {
    document.getElementById('messages').innerHTML = `
      <div id="welcome">
        <div class="welcome-icon">⚡</div>
        <h1>מה נפתור היום?</h1>
        <p>מבחני מהט, תאוריה, ופתרון שלב-אחר-שלב</p>
        <div class="chips">
          <div class="chip" onclick="sendChip(this)">🔌 שנאי 10kVA — חשב זרמים</div>
          <div class="chip" onclick="sendChip(this)">⚙️ אסינכרוני — מהירות סינכרונית</div>
          <div class="chip" onclick="sendChip(this)">🔋 מנוע DC — חשב EMF</div>
          <div class="chip" onclick="sendChip(this)">📖 ניסוי ריקם vs ניסוי קצר</div>
        </div>
      </div>`;
  }

  // ========== MESSAGING ==========
  function sendChip(el) {
    const text = el.innerText;
    document.getElementById('user-input').value = text;
    sendMessage();
  }

  function handleKey(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  }

  function autoResize(el) {
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 160) + 'px';
  }

  // ========== IMAGE HANDLING ==========
  function onImageSelected(event) {
    const file = event.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
      const dataUrl = e.target.result;
      // dataUrl = "data:image/jpeg;base64,XXXX..."
      const [header, base64] = dataUrl.split(',');
      const mimeType = header.match(/:(.*?);/)[1];

      pendingImage = { base64, mimeType, dataUrl, name: file.name };

      // Show preview
      document.getElementById('image-preview').src = dataUrl;
      document.getElementById('image-preview-name').textContent = file.name;
      document.getElementById('image-preview-wrap').classList.add('visible');
      document.getElementById('attach-btn').classList.add('has-image');
    };
    reader.readAsDataURL(file);

    // Reset input so same file can be re-selected
    event.target.value = '';
  }

  function removeImage() {
    pendingImage = null;
    document.getElementById('image-preview-wrap').classList.remove('visible');
    document.getElementById('attach-btn').classList.remove('has-image');
    document.getElementById('image-preview').src = '';
  }

  async function sendMessage() {
    const input = document.getElementById('user-input');
    const text = input.value.trim();
    if ((!text && !pendingImage) || isLoading) return;

    // Clear welcome
    const welcome = document.getElementById('welcome');
    if (welcome) welcome.remove();

    // Show user message (with image thumbnail if attached)
    appendMessage('user', text, pendingImage ? pendingImage.dataUrl : null);
    input.value = '';
    input.style.height = 'auto';

    // Capture and clear pending image
    const imageToSend = pendingImage;
    removeImage();

    // Create streaming bot bubble
    const botBubble = createStreamingBubble();

    isLoading = true;
    document.getElementById('send-btn').disabled = true;

    try {
      const body = {
        message: text,
        conversation_id: currentConvId
      };
      if (imageToSend) {
        body.image_data = imageToSend.base64;
        body.image_mime_type = imageToSend.mimeType;
      }

      const res = await apiFetch('/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({ detail: 'Server error' }));
        throw new Error(errData.detail || 'Server error');
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let fullText = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n\n');
        buffer = parts.pop();

        for (const part of parts) {
          if (!part.startsWith('data: ')) continue;
          let parsed;
          try { parsed = JSON.parse(part.slice(6)); } catch { continue; }

          if (parsed.conversation_id) {
            const isNew = !currentConvId;
            currentConvId = parsed.conversation_id;
            if (isNew) loadConversations();
          }
          if (parsed.chunk) {
            fullText += parsed.chunk;
            updateStreamingBubble(botBubble, fullText);
          }
          if (parsed.error) {
            finalizeStreamingBubble(botBubble, `❌ שגיאה: ${parsed.error}`, true);
          }
          if (parsed.done) {
            finalizeStreamingBubble(botBubble, fullText);
          }
        }
      }

    } catch (e) {
      finalizeStreamingBubble(botBubble, `❌ שגיאה: ${e.message}`, true);
    } finally {
      isLoading = false;
      document.getElementById('send-btn').disabled = false;
      input.focus();
    }
  }

  function createStreamingBubble() {
    const messagesEl = document.getElementById('messages');
    const msgEl = document.createElement('div');
    msgEl.className = 'message bot';
    msgEl.innerHTML = `
      <div class="avatar">⚡</div>
      <div class="bubble" dir="auto">
        <div class="typing-indicator">
          <span></span><span></span><span></span>
        </div>
      </div>
    `;
    messagesEl.appendChild(msgEl);
    scrollToBottom();
    return msgEl.querySelector('.bubble');
  }

  function extractCompleteTextForStreaming(text) {
    // Find unclosed $$
    const blockMathParts = text.split('$$');
    if (blockMathParts.length % 2 === 0) {
      // Unclosed block math
      const pendingIdx = text.lastIndexOf('$$');
      return { safe: text.slice(0, pendingIdx), pending: text.slice(pendingIdx) };
    }
    
    // Find unclosed \\[
    const bracketOpen = text.lastIndexOf('\\[');
    const bracketClose = text.lastIndexOf('\\]');
    if (bracketOpen > bracketClose) {
      return { safe: text.slice(0, bracketOpen), pending: text.slice(bracketOpen) };
    }
    
    // Find unclosed \\(
    const parenOpen = text.lastIndexOf('\\(');
    const parenClose = text.lastIndexOf('\\)');
    if (parenOpen > parenClose) {
      return { safe: text.slice(0, parenOpen), pending: text.slice(parenOpen) };
    }

    return { safe: text, pending: '' };
  }

  let _mathRenderTimer = null;
  function updateStreamingBubble(bubble, text) {
    const { safe, pending } = extractCompleteTextForStreaming(text);
    bubble.innerHTML = renderMarkdown(safe) + 
       (pending ? '<span style="color:var(--accent);opacity:0.8">' + escapeHtml(pending) + '</span>' : '') + 
       '<span class="cursor-blink">▍</span>';
       
    // Debounce math rendering to avoid flicker during streaming
    clearTimeout(_mathRenderTimer);
    _mathRenderTimer = setTimeout(() => renderMath(bubble), 50);
    scrollToBottom();
  }

  function finalizeStreamingBubble(bubble, text, isError = false) {
    if (isError) {
      bubble.innerHTML = escapeHtml(text);
    } else {
      bubble.innerHTML = renderMarkdown(text);
      renderMath(bubble);
      addBubbleActions(bubble);
    }
    scrollToBottom();
  }

  // ========== CORRECT SOLUTION UPLOAD ==========
  function addBubbleActions(bubble) {
    const actions = document.createElement('div');
    actions.className = 'bubble-actions';
    actions.innerHTML = `
      <button class="action-btn" onclick="copyBubble(this)" title="העתק">📋 העתק</button>
      <button class="save-to-bank-btn" onclick="saveChatToBank(this)" title="שמור תשובה לבנק התרגילים">💾 שמור לבנק</button>
      <button class="action-btn" onclick="requestCorrectSolution()" title="העלה תמונה של הפתרון הנכון">📄 פתרון נכון</button>
    `;
    bubble.appendChild(actions);
  }

  function copyBubble(btn) {
    const bubble = btn.closest('.bubble');
    const text = bubble.innerText.replace(/📋 העתק|📄 פתרון נכון/g, '').trim();
    navigator.clipboard.writeText(text).then(() => {
      btn.classList.add('copied');
      btn.textContent = '✓ הועתק';
      setTimeout(() => { btn.classList.remove('copied'); btn.textContent = '📋 העתק'; }, 2000);
    });
  }

  function requestCorrectSolution() {
    document.getElementById('correct-solution-input').click();
  }

  function onCorrectSolutionSelected(event) {
    const file = event.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (e) => {
      const dataUrl = e.target.result;
      const [header, base64] = dataUrl.split(',');
      const mimeType = header.match(/:(.*?);/)[1];
      pendingImage = { base64, mimeType, dataUrl, name: file.name };
      document.getElementById('user-input').value = 'הנה הפתרון הנכון. השווה לתשובה שנתת קודם, זהה בדיוק היכן טעית ותקן עם הסבר מלא.';
      sendMessage();
    };
    reader.readAsDataURL(file);
    event.target.value = '';
  }

  function appendMessage(role, content, imageDataUrl = null) {
    const messagesEl = document.getElementById('messages');

    const msgEl = document.createElement('div');
    msgEl.className = `message ${role}`;

    const avatar = role === 'user' ? '👤' : '⚡';
    const now = new Date();
    const timeStr = now.toLocaleTimeString('he-IL', { hour: '2-digit', minute: '2-digit' });

    let bubbleContent = '';
    if (imageDataUrl) {
      bubbleContent += `<img class="msg-image" src="${imageDataUrl}" alt="תמונה מצורפת" />`;
    }
    bubbleContent += role === 'bot'
      ? renderMarkdown(content)
      : escapeHtml(content).replace(/\n/g, '<br>');

    msgEl.innerHTML = `
      <div class="avatar">${avatar}</div>
      <div>
        <div class="bubble" dir="auto">${bubbleContent}</div>
        <div class="msg-time">${timeStr}</div>
      </div>
    `;

    messagesEl.appendChild(msgEl);

    // Render math in bot messages
    if (role === 'bot') {
      const bubble = msgEl.querySelector('.bubble');
      renderMath(bubble);
      addBubbleActions(bubble);
    }

    scrollToBottom();
  }

  function showTyping() {
    const messagesEl = document.getElementById('messages');
    const id = 'typing-' + Date.now();

    const el = document.createElement('div');
    el.className = 'message bot';
    el.id = id;
    el.innerHTML = `
      <div class="avatar">⚡</div>
      <div class="bubble">
        <div class="typing-indicator">
          <span></span><span></span><span></span>
        </div>
      </div>
    `;

    messagesEl.appendChild(el);
    scrollToBottom();
    return id;
  }

  function removeTyping(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
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

    marked.setOptions({ breaks: true, gfm: true });
    let html = marked.parse(protected_text);

    // Restore math blocks (un-escape any HTML entities in placeholders)
    html = html.replace(/%%MATH_BLOCK_(\d+)%%/g, (_, idx) => mathBlocks[parseInt(idx)] || '');

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

  // ========== QUESTION BANK ==========
  let qbankOpen = false;

  function toggleQBank() {
    qbankOpen = !qbankOpen;
    document.getElementById('qbank-panel').style.display = qbankOpen ? 'block' : 'none';
    if (qbankOpen) loadQBank();
  }

  async function loadQBank() {
    try {
      const res = await apiFetch('/api/questions');
      const questions = await res.json();
      renderQBank(questions);
    } catch (e) {
      document.getElementById('qbank-list').innerHTML = '<div class="qbank-empty">שגיאה בטעינה</div>';
    }
  }

  function renderQBank(questions) {
    const badge = document.getElementById('qbank-count-badge');
    if (questions.length) {
      badge.textContent = questions.length;
      badge.style.display = '';
    } else {
      badge.style.display = 'none';
    }

    const list = document.getElementById('qbank-list');
    if (!questions.length) {
      list.innerHTML = '<div class="qbank-empty">אין שאלות עדיין — חלץ ממבחנים או מתמונה</div>';
      return;
    }

    // Group by topic
    const groups = {};
    questions.forEach(q => {
      const topic = q.topic || 'כללי';
      if (!groups[topic]) groups[topic] = [];
      groups[topic].push(q);
    });

    const topicIcons = {
      'שנאים': '🔌', 'שנאי': '🔌',
      'מנוע אסינכרוני': '⚙️', 'אסינכרוני': '⚙️', 'מנוע השראה': '⚙️',
      'גנרטור סינכרוני': '🔄', 'סינכרוני': '🔄', 'מנוע סינכרוני': '🔄',
      'DC': '🔋', 'מנוע DC': '🔋', 'גנרטור DC': '🔋',
      'הינע חשמלי': '🏭', 'כללי': '📋'
    };

    const getIcon = (topic) => {
      for (const [key, icon] of Object.entries(topicIcons)) {
        if (topic.includes(key)) return icon;
      }
      return '📋';
    };

    list.innerHTML = Object.entries(groups).map(([topic, qs]) => `
      <div class="qbank-topic-group">
        <div class="qbank-topic-header" onclick="this.parentElement.classList.toggle('collapsed')">
          <span>${getIcon(topic)} ${escapeHtml(topic)}</span>
          <span class="qbank-topic-count">${qs.length}</span>
        </div>
        <div class="qbank-topic-items">
          ${qs.map(q => `
            <div class="qbank-item">
              ${q.image_url ? `<img class="qbank-img" src="${q.image_url}" onclick="openLightbox('${q.image_url}')" alt="תמונת שאלה" />` : ''}
              <div class="qbank-text">${escapeHtml(q.text)}</div>
              ${q.solution ? `
                <button class="qbank-toggle-solution" onclick="toggleSolution(this)">▼ הצג פתרון</button>
                <div class="qbank-solution">${escapeHtml(q.solution)}</div>
              ` : ''}
              <div class="qbank-item-actions">
                <button class="qbank-ask-btn" onclick="askQuestion('${encodeURIComponent(q.text)}')">▶ שאל</button>
                <button class="qbank-del-btn" onclick="deleteQuestion(${q.id})">✕</button>
              </div>
            </div>
          `).join('')}
        </div>
      </div>
    `).join('');
  }

  function toggleSolution(btn) {
    const sol = btn.nextElementSibling;
    const visible = sol.classList.toggle('visible');
    btn.textContent = visible ? '▲ הסתר פתרון' : '▼ הצג פתרון';
  }

  async function deleteQuestion(id) {
    await apiFetch(`/api/questions/${id}`, { method: 'DELETE' });
    loadQBank();
  }

  function askQuestion(encodedText) {
    const text = decodeURIComponent(encodedText);
    newChat();
    document.getElementById('user-input').value = text;
    document.getElementById('user-input').focus();
    autoResize(document.getElementById('user-input'));
  }

  // ========== EXAM PICKER ==========
  function openExamPicker() {
    const overlay = document.getElementById('exam-picker-overlay');
    overlay.classList.add('active');
    loadExamList();
  }
  function closeExamPicker() {
    document.getElementById('exam-picker-overlay').classList.remove('active');
  }

  async function loadExamList() {
    const listEl = document.getElementById('exam-picker-list');
    listEl.innerHTML = '<div style="text-align:center;padding:30px;color:var(--text-muted)">טוען מבחנים...</div>';
    try {
      const res = await apiFetch('/api/exams');
      const exams = await res.json();
      if (!exams.length) {
        listEl.innerHTML = '<div style="text-align:center;padding:30px;color:var(--text-muted)">לא נמצאו קבצי מבחנים</div>';
        return;
      }
      // Group by exam code
      const groups = {};
      exams.forEach(e => {
        if (!groups[e.code]) groups[e.code] = [];
        groups[e.code].push(e);
      });
      let html = '';
      for (const [code, items] of Object.entries(groups)) {
        const groupName = items[0].label.split('—')[0].trim();
        html += `<div class="exam-group-label">${groupName} (${code}) — ${items.length} מבחנים</div>`;
        items.forEach(e => {
          const icon = e.has_pdf ? '📷' : '📄';
          const pdfBadge = e.has_pdf ? '<span style="font-size:10px;background:rgba(34,197,94,0.15);color:#22c55e;padding:2px 6px;border-radius:4px;margin-right:6px">כולל סרטוטים</span>' : '';
          html += `<div class="exam-item" onclick="pickExam('${e.file}', this)">
            <span class="exam-icon">${icon}</span>
            <span class="exam-label">${e.label} ${pdfBadge}</span>
          </div>`;
        });
      }
      listEl.innerHTML = html;
    } catch (e) {
      listEl.innerHTML = `<div style="text-align:center;padding:30px;color:#ef4444">שגיאה: ${e.message}</div>`;
    }
  }

  async function pickExam(filename, itemEl) {
    // Disable all items during extraction
    const allItems = document.querySelectorAll('.exam-item');
    allItems.forEach(el => { el.style.pointerEvents = 'none'; el.style.opacity = '0.5'; });
    if (itemEl) {
      itemEl.style.opacity = '1';
      itemEl.innerHTML = `<span class="exam-icon">⏳</span><span class="exam-label">מחלץ, מתייג ופותר שאלות... (עד 5 דקות)</span>`;
    }

    try {
      const res = await apiFetch('/api/questions/extract-exams', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ exam_file: filename })
      });
      const data = await res.json();
      const method = data.method || 'text';
      const saved = data.saved || 0;
      const dupes = data.duplicates || 0;
      const solved = data.solved || 0;
      const extracted = data.extracted || 0;

      loadExerciseBank();
      loadQBank();
      closeExamPicker();

      const imgNote = method === 'pdf_vision' ? ' 📷' : '';
      if (saved > 0) {
        showToast(`✅ חילוץ הושלם!${imgNote} ${saved} שאלות נשמרו, ${solved} נפתרו אוטומטית.${dupes ? ` (${dupes} כפילויות דולגו)` : ''}`, 'success');
      } else if (dupes > 0) {
        showToast(`כל ${dupes} השאלות כבר קיימות במאגר.`, 'info');
      } else if (extracted === 0) {
        showToast('לא נמצאו שאלות במבחן הזה.', 'info');
      } else {
        showToast('לא נמצאו שאלות חדשות.', 'info');
      }
    } catch (e) {
      showToast('שגיאה: ' + e.message, 'error');
    } finally {
      // Re-enable items
      allItems.forEach(el => { el.style.pointerEvents = ''; el.style.opacity = ''; });
      loadExamList(); // refresh list
    }
  }

  // ========== LOCAL EXAM PICKER ==========
  function openLocalExamPicker() {
    document.getElementById('local-exam-picker-overlay').classList.add('active');
    // Reset UI
    document.getElementById('pdf-drop-zone').style.display = '';
    document.getElementById('pdf-upload-status').style.display = 'none';
    document.getElementById('pdf-file-input').value = '';
  }
  function closeLocalExamPicker() {
    document.getElementById('local-exam-picker-overlay').classList.remove('active');
  }

  function handlePdfDrop(event) {
    event.preventDefault();
    document.getElementById('pdf-drop-zone').classList.remove('dragover');
    const file = event.dataTransfer.files[0];
    if (file) uploadPdfFile(file);
  }

  function handlePdfFileSelected(event) {
    const file = event.target.files[0];
    if (file) uploadPdfFile(file);
  }

  async function uploadPdfFile(file) {
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      showToast('יש לבחור קובץ PDF בלבד', 'error'); return;
    }
    if (file.size > 20 * 1024 * 1024) {
      showToast('הקובץ גדול מדי (מקסימום 20MB)', 'error'); return;
    }

    const dropZone = document.getElementById('pdf-drop-zone');
    const statusEl = document.getElementById('pdf-upload-status');
    dropZone.style.display = 'none';
    statusEl.style.display = 'block';
    statusEl.innerHTML = `<div style="font-size:2rem;margin-bottom:12px">⏳</div>
      <div style="font-weight:600;margin-bottom:6px">מעלה ומחלץ שאלות...</div>
      <div style="font-size:0.8rem;color:var(--text-muted)">${escapeHtml(file.name)} · ${(file.size/1024).toFixed(0)}KB</div>
      <div style="margin-top:12px;font-size:0.8rem;color:var(--text-muted)">תהליך זה עשוי לקחת עד 5 דקות</div>`;

    try {
      const formData = new FormData();
      formData.append('file', file);
      const token = localStorage.getItem('authToken');
      const headers = token ? { 'Authorization': 'Bearer ' + token } : {};
      const res = await fetch('/api/questions/upload-pdf', { method: 'POST', headers, body: formData });
      const data = await res.json();
      if (!res.ok) { showToast('שגיאה: ' + (data.detail || res.status), 'error'); return; }

      const { saved = 0, duplicates = 0, solved = 0 } = data;
      loadExerciseBank();
      closeLocalExamPicker();
      if (saved > 0) {
        showToast(`✅ ${saved} שאלות נשמרו, ${solved} נפתרו.${duplicates ? ` (${duplicates} כפילויות דולגו)` : ''}`, 'success');
      } else if (duplicates > 0) {
        showToast(`כל ${duplicates} השאלות כבר קיימות במאגר.`, 'info');
      } else {
        showToast('לא נמצאו שאלות חדשות בקובץ.', 'info');
      }
    } catch (e) {
      showToast('שגיאה: ' + e.message, 'error');
      dropZone.style.display = '';
      statusEl.style.display = 'none';
    }
  }

  async function extractFromImageFile(event) {
    const file = event.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = async (e) => {
      const dataUrl = e.target.result;
      const [header, base64] = dataUrl.split(',');
      const mimeType = header.match(/:(.*?);/)[1];
      try {
        const res = await apiFetch('/api/questions/extract-image', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: '', image_data: base64, image_mime_type: mimeType })
        });
        const data = await res.json();
        showExtractedQuestions(data.questions, file.name, data.image_url || '');
      } catch (e) {
        showToast('שגיאה: ' + e.message, 'error');
      }
    };
    reader.readAsDataURL(file);
    event.target.value = '';
  }

  function showExtractedQuestions(questions, source, imageUrl) {
    const list = document.getElementById('qbank-list');
    if (!questions || !questions.length) {
      list.innerHTML = '<div class="qbank-empty">לא נמצאו שאלות</div>';
      return;
    }
    const imgAttr = imageUrl ? ` data-image-url="${escapeHtml(imageUrl)}"` : '';
    const itemsHtml = questions.map((q, i) => {
      const text = typeof q === 'string' ? q : q.text;
      const topic = typeof q === 'string' ? '' : (q.topic || '');
      return `<div class="extracted-item">
        <label>
          <input type="checkbox" checked data-text="${escapeHtml(text)}" data-topic="${escapeHtml(topic)}"${imgAttr}>
          <span>${escapeHtml(text)}${topic ? ` <em style="color:var(--text-muted)">(${escapeHtml(topic)})</em>` : ''}</span>
        </label>
      </div>`;
    }).join('');

    list.innerHTML = `
      <div class="extracted-panel">
        ${imageUrl ? `<img class="extracted-preview-img" src="${imageUrl}" onclick="openLightbox('${imageUrl}')" alt="תמונת מקור" />` : ''}
        <div class="extracted-title">נמצאו ${questions.length} שאלות מ${escapeHtml(source)}:</div>
        ${itemsHtml}
        <div class="extracted-actions">
          <button class="qbank-btn" onclick="saveSelectedQuestions('${escapeHtml(source)}')">💾 שמור מסומנים</button>
          <button class="qbank-btn" onclick="loadQBank()">ביטול</button>
        </div>
      </div>`;
  }

  async function saveSelectedQuestions(source) {
    const checkboxes = document.querySelectorAll('.extracted-item input[type=checkbox]:checked');
    await Promise.all(Array.from(checkboxes).map(cb =>
      apiFetch('/api/questions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: cb.dataset.text,
          topic: cb.dataset.topic,
          source,
          solution: cb.dataset.solution || '',
          image_url: cb.dataset.imageUrl || ''
        })
      })
    ));
    loadQBank();
    loadExerciseBank();
  }

  function scrollToBottom() {
    const el = document.getElementById('messages');
    el.scrollTop = el.scrollHeight;
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