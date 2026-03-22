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

