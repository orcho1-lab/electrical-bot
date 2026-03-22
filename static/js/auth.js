  // ========== INIT ==========
  // ========== AUTH: LOGIN ==========
  let currentAuthMode = 'login';

  function setAuthMode(mode) {
    currentAuthMode = mode;
    const isReg = mode === 'register';
    
    // Update tabs
    document.getElementById('auth-tab-login').style.background = isReg ? 'transparent' : '#7c6af7';
    document.getElementById('auth-tab-login').style.color = isReg ? 'rgba(255,255,255,0.5)' : '#fff';
    document.getElementById('auth-tab-register').style.background = isReg ? '#7c6af7' : 'transparent';
    document.getElementById('auth-tab-register').style.color = isReg ? '#fff' : 'rgba(255,255,255,0.5)';
    
    // Update labels
    document.getElementById('login-title').textContent = isReg ? 'יצירת חשבון חדש' : 'ברוכים השבים';
    document.getElementById('login-subtitle').textContent = isReg ? 'הכנס פרטים כדי להצטרף לקהילת הלומדים' : 'הכנס אימייל וסיסמה כדי להמשיך';
    document.getElementById('login-submit-btn').textContent = isReg ? 'הרשמה' : 'כניסה';
    
    // Update fields
    document.getElementById('login-code-wrapper').style.display = isReg ? 'block' : 'none';
    document.getElementById('login-error').textContent = '';
  }

  function showLoginScreen() {
    document.getElementById('login-overlay').style.display = 'flex';
    setAuthMode('login'); // Always default to login
  }

  function hideLoginScreen() {
    document.getElementById('login-overlay').style.display = 'none';
  }

  async function doLogin() {
    const em = document.getElementById('login-email').value;
    const pw = document.getElementById('login-password').value;
    const code = document.getElementById('login-code').value;
    const errEl = document.getElementById('login-error');
    if (currentAuthMode === 'register' && !code) {
      errEl.textContent = 'נא להזין קוד הרשמה';
      return;
    }
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

