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
    const code = document.getElementById('login-code').value;
    const errEl = document.getElementById('login-error');
    errEl.textContent = '';
    if (!em || !pw) { errEl.textContent = 'נא להזין אימייל וסיסמה'; return; }
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: em, password: pw, code: code || undefined })
      });
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        errEl.textContent = errorData.detail || 'שגיאת התחברות';
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

