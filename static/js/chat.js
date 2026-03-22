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

