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

