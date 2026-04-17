/* ============================================================
   AgriChain CRM — Main JavaScript
   ============================================================ */

// ── Modal Management ──────────────────────────────────────

function openModal(id) {
  const modal = document.getElementById(id);
  if (modal) {
    modal.classList.remove('hidden');
    document.body.style.overflow = 'hidden';
  }
}

function closeModal(id) {
  const modal = document.getElementById(id);
  if (modal) {
    modal.classList.add('hidden');
    document.body.style.overflow = '';
  }
}

// Close modal on Escape key
document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') {
    document.querySelectorAll('.modal:not(.hidden)').forEach(m => {
      m.classList.add('hidden');
      document.body.style.overflow = '';
    });
    closeSearch();
  }
});

// ── Global Search ─────────────────────────────────────────

function openSearch() {
  const overlay = document.getElementById('search-overlay');
  if (overlay) {
    overlay.classList.remove('hidden');
    const input = document.getElementById('global-search-input');
    if (input) {
      input.value = '';
      input.focus();
    }
    document.getElementById('search-results').innerHTML = '';
  }
}

function closeSearch() {
  const overlay = document.getElementById('search-overlay');
  if (overlay) overlay.classList.add('hidden');
}

let searchTimer = null;

const searchInput = document.getElementById('global-search-input');
if (searchInput) {
  searchInput.addEventListener('input', function() {
    clearTimeout(searchTimer);
    const q = this.value.trim();
    if (q.length < 2) {
      document.getElementById('search-results').innerHTML = '';
      return;
    }
    searchTimer = setTimeout(() => performSearch(q), 300);
  });
}

async function performSearch(q) {
  try {
    const res = await fetch('/search?q=' + encodeURIComponent(q));
    const data = await res.json();
    renderSearchResults(data);
  } catch (e) {
    console.error('Search error:', e);
  }
}

function renderSearchResults(data) {
  const container = document.getElementById('search-results');
  if (!container) return;
  container.innerHTML = '';

  const hasResults = data.leads.length || data.contacts.length || data.companies.length;
  if (!hasResults) {
    container.innerHTML = '<div style="padding:1rem;text-align:center;color:var(--text-muted);font-size:0.875rem;">No results found</div>';
    return;
  }

  if (data.leads.length) {
    const title = document.createElement('div');
    title.className = 'search-group-title';
    title.textContent = 'Leads';
    container.appendChild(title);
    data.leads.forEach(l => {
      const a = document.createElement('a');
      a.href = '/leads/' + l.id;
      a.className = 'search-result-item';
      a.innerHTML = `<div>${l.name}</div><div class="search-result-sub">${l.company || ''}</div>`;
      a.onclick = closeSearch;
      container.appendChild(a);
    });
  }

  if (data.contacts.length) {
    const title = document.createElement('div');
    title.className = 'search-group-title';
    title.textContent = 'Contacts';
    container.appendChild(title);
    data.contacts.forEach(c => {
      const a = document.createElement('a');
      a.href = '/contacts/' + c.id;
      a.className = 'search-result-item';
      a.innerHTML = `<div>${c.name}</div><div class="search-result-sub">${c.email || ''}</div>`;
      a.onclick = closeSearch;
      container.appendChild(a);
    });
  }

  if (data.companies.length) {
    const title = document.createElement('div');
    title.className = 'search-group-title';
    title.textContent = 'Companies';
    container.appendChild(title);
    data.companies.forEach(co => {
      const a = document.createElement('a');
      a.href = '/companies/' + co.id;
      a.className = 'search-result-item';
      a.innerHTML = `<div>${co.name}</div>`;
      a.onclick = closeSearch;
      container.appendChild(a);
    });
  }
}

// ── Flash message auto-dismiss ────────────────────────────

setTimeout(() => {
  document.querySelectorAll('.flash').forEach(f => {
    f.style.transition = 'opacity 0.5s';
    f.style.opacity = '0';
    setTimeout(() => f.remove(), 500);
  });
}, 4000);

// ── Keyboard shortcut: Ctrl+K / Cmd+K to open search ─────

document.addEventListener('keydown', function(e) {
  if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
    e.preventDefault();
    openSearch();
  }
});
