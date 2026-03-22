// static/js/learnings.js

async function openLearningsModal() {
  document.getElementById('learnings-modal').classList.add('active');
  await fetchLearnings();
}

function closeLearningsModal() {
  document.getElementById('learnings-modal').classList.remove('active');
}

async function fetchLearnings() {
  const listEl = document.getElementById('learnings-list');
  listEl.innerHTML = '<div style="text-align:center;padding:20px;color:var(--text-muted)">טוען לקחים...</div>';
  
  try {
    const res = await apiFetch('/api/learnings');
    if (!res.ok) throw new Error('Failed to fetch');
    const learnings = await res.json();
    
    if (learnings.length === 0) {
      listEl.innerHTML = '<div style="text-align:center;padding:20px;color:var(--text-muted)">אין לקחים שמורים עדיין. הבוט צובר לקחים כשהוא מתקן טעויות.</div>';
      return;
    }
    
    listEl.innerHTML = learnings.map(l => `
      <div class="learning-item" id="learning-${l.id}">
        <div class="learning-text">${escapeHtml(l.summary)}</div>
        <button class="action-btn" style="color:#ef4444" onclick="deleteLearning(${l.id})" title="מחק לקח">🗑️ מחיקה</button>
      </div>
    `).join('');
    
  } catch (e) {
    listEl.innerHTML = '<div style="color:#ef4444;text-align:center;">שגיאה בטעינת הלקחים</div>';
  }
}

async function deleteLearning(id) {
  if (!confirm('האם אתה בטוח שברצונך למחוק לקח זה? הבוט עלול לחזור על טעויות עבר.')) return;
  
  try {
    const res = await apiFetch('/api/learnings/' + id, { method: 'DELETE' });
    if (!res.ok) throw new Error('Failed to delete');
    
    document.getElementById('learning-' + id).remove();
    showToast('הלקח נמחק בהצלחה', 'success');
  } catch (e) {
    showToast('שגיאה במחיקת לקח', 'error');
  }
}
