// Shared helpers for every page.

async function api(path, options = {}) {
  const opts = { ...options };
  if (opts.json !== undefined) {
    opts.method = opts.method || 'POST';
    opts.headers = { 'Content-Type': 'application/json', ...(opts.headers || {}) };
    opts.body = JSON.stringify(opts.json);
    delete opts.json;
  }
  const res = await fetch(path, opts);
  if (res.status === 204) return null;
  const data = await res.json().catch(() => ({}));
  // Session expired or signed out in another tab: go back to sign-in.
  if (res.status === 401 && location.pathname !== '/login') {
    location.href = '/login';
  }
  if (!res.ok) throw new Error(data.detail || `Request failed (${res.status})`);
  return data;
}

document.addEventListener('DOMContentLoaded', () => {
  const logout = document.getElementById('logout-btn');
  if (logout) {
    logout.addEventListener('click', async () => {
      const data = await api('/api/logout', { method: 'POST' });
      location.href = data.redirect;
    });
  }
});

function toast(message) {
  const el = document.getElementById('toast');
  el.textContent = message;
  el.classList.remove('hidden');
  clearTimeout(toast._t);
  toast._t = setTimeout(() => el.classList.add('hidden'), 2800);
}

// Disable a button and show a spinner while an async action runs.
async function withBusy(button, fn) {
  const original = button.innerHTML;
  button.disabled = true;
  button.innerHTML = '<span class="spinner"></span>Working…';
  try {
    return await fn();
  } catch (e) {
    toast(e.message);
  } finally {
    button.disabled = false;
    button.innerHTML = original;
  }
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}
