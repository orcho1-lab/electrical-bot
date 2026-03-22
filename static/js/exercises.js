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
              <div class="eb-solution-wrap" data-qid="${q.id}" data-raw="${escapeAttr(q.solution)}"></div>
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

    // Render markdown + math on first open (read from data-raw, not textContent)
    if (isOpen && !wrap.dataset.rendered) {
      const raw = wrap.dataset.raw || '';
      wrap.innerHTML = renderMarkdown(raw);
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

