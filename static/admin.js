const adminState = {
  secret: '',
  overview: null,
};

const statusEl = document.getElementById('adminStatus');
const secretInput = document.getElementById('secretInput');
const loadBtn = document.getElementById('loadOverview');

const symbolListEl = document.getElementById('symbolList');
const symbolForm = document.getElementById('symbolForm');
const wheelListEl = document.getElementById('wheelList');
const wheelForm = document.getElementById('wheelForm');
const shopListEl = document.getElementById('shopList');
const shopForm = document.getElementById('shopForm');
const eventsListEl = document.getElementById('eventsList');
const eventForm = document.getElementById('eventForm');
const rewardLinkForm = document.getElementById('rewardLinkForm');
const broadcastForm = document.getElementById('broadcastForm');
const rewardLinkResult = document.getElementById('rewardLinkResult');
const rewardLinkList = document.getElementById('rewardLinkList');
const broadcastList = document.getElementById('broadcastList');
const leaderboardPreview = document.getElementById('leaderboardPreview');
const leaderboardRewardForm = document.getElementById('leaderboardRewardForm');
const resetLeaderboardBtn = document.getElementById('resetLeaderboard');

function setStatus(message, isError = false) {
  if (!statusEl) return;
  statusEl.textContent = message || '';
  statusEl.style.color = isError ? '#f87171' : '#facc15';
}

async function loadOverview(silent = false) {
  const secret = secretInput.value.trim();
  if (!secret) {
    if (!silent) setStatus('Enter the admin secret to continue.', true);
    return;
  }
  adminState.secret = secret;
  sessionStorage.setItem('sharkspin-admin-secret', secret);
  try {
    const res = await fetch('/admin/api/overview', {
      headers: { 'X-Admin-Secret': secret },
    });
    const data = await res.json();
    if (!res.ok || !data.ok) {
      throw new Error(data.error || 'Unable to load dashboard');
    }
    adminState.overview = data;
    renderOverview();
    if (!silent) setStatus('Dashboard refreshed.');
  } catch (err) {
    setStatus(err.message, true);
  }
}

function adminPayloadFromForm(form) {
  const data = new FormData(form);
  const payload = {};
  for (const [key, value] of data.entries()) {
    if (value === '' || value === null) continue;
    if (key === 'is_active') {
      payload[key] = form.elements[key].checked;
    } else {
      payload[key] = value;
    }
  }
  return payload;
}

async function adminRequest(method, url, payload) {
  if (!adminState.secret) throw new Error('Admin secret missing. Load the overview first.');
  const options = {
    method,
    headers: {
      'Content-Type': 'application/json',
      'X-Admin-Secret': adminState.secret,
    },
  };
  if (payload) {
    options.body = JSON.stringify(payload);
  }
  const res = await fetch(url, options);
  let data = {};
  try {
    data = await res.json();
  } catch (err) {
    /* ignore */
  }
  if (!res.ok || data.ok === false) {
    throw new Error(data.error || 'Request failed');
  }
  return data;
}

function clearForm(form) {
  form.reset();
  if (form.elements.id) {
    form.elements.id.value = '';
  }
}

function renderOverview() {
  const data = adminState.overview;
  if (!data) return;
  renderSymbols(data.symbols || []);
  renderWheel(data.wheel_rewards || []);
  renderShop(data.shop || []);
  renderEvents(data.events || []);
  renderRewardHistory(data.reward_links || [], data.broadcasts || []);
  renderLeaderboardPreview(data.leaderboard || []);
}

function renderSymbols(symbols) {
  if (!symbolListEl) return;
  symbolListEl.innerHTML = '';
  symbols.forEach((symbol) => {
    const pill = document.createElement('div');
    pill.className = 'pill';
    pill.style.borderColor = symbol.color || '#38bdf8';
    pill.innerHTML = `
      <div class="meta">
        <strong>${symbol.emoji} ${symbol.name}</strong>
        <span>Weight ${symbol.weight.toFixed(2)} • Coins ${symbol.coins} • Energy ${symbol.energy} • Tokens ${symbol.wheel_tokens}</span>
      </div>
      <div class="actions">
        <button data-action="edit">Edit</button>
        <button data-action="disable">Disable</button>
      </div>
    `;
    pill.querySelector('[data-action="edit"]').addEventListener('click', () => fillSymbolForm(symbol));
    pill.querySelector('[data-action="disable"]').addEventListener('click', async () => {
      try {
        await adminRequest('DELETE', `/admin/api/slot-symbols/${symbol.id}`);
        await loadOverview(true);
        setStatus(`Symbol ${symbol.name} disabled.`);
      } catch (err) {
        setStatus(err.message, true);
      }
    });
    symbolListEl.appendChild(pill);
  });
}

function fillSymbolForm(symbol) {
  if (!symbolForm) return;
  const fields = ['id', 'emoji', 'name', 'weight', 'coins', 'energy', 'wheel_tokens', 'description', 'art_url', 'sort_order', 'color'];
  fields.forEach((field) => {
    if (symbolForm.elements[field]) {
      symbolForm.elements[field].value = symbol[field] ?? '';
    }
  });
}

if (symbolForm) {
  symbolForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    try {
      const payload = adminPayloadFromForm(symbolForm);
      if (payload.weight !== undefined) payload.weight = parseFloat(payload.weight);
      ['coins', 'energy', 'wheel_tokens', 'sort_order'].forEach((key) => {
        if (payload[key] !== undefined) payload[key] = parseInt(payload[key], 10);
      });
      await adminRequest('POST', '/admin/api/slot-symbols', payload);
      clearForm(symbolForm);
      await loadOverview(true);
      setStatus('Symbol saved.');
    } catch (err) {
      setStatus(err.message, true);
    }
  });
}

function renderWheel(rewards) {
  if (!wheelListEl) return;
  wheelListEl.innerHTML = '';
  rewards.forEach((reward) => {
    const pill = document.createElement('div');
    pill.className = 'pill';
    pill.style.borderColor = reward.color || '#22d3ee';
    pill.innerHTML = `
      <div class="meta">
        <strong>${reward.label}</strong>
        <span>${reward.reward_type} • Amount ${reward.amount} • Weight ${reward.weight.toFixed(2)}</span>
      </div>
      <div class="actions">
        <button data-action="edit">Edit</button>
        <button data-action="delete">Delete</button>
      </div>
    `;
    pill.querySelector('[data-action="edit"]').addEventListener('click', () => fillWheelForm(reward));
    pill.querySelector('[data-action="delete"]').addEventListener('click', async () => {
      try {
        await adminRequest('DELETE', `/admin/api/wheel-rewards/${reward.id}`);
        await loadOverview(true);
        setStatus('Wheel reward removed.');
      } catch (err) {
        setStatus(err.message, true);
      }
    });
    wheelListEl.appendChild(pill);
  });
}

function fillWheelForm(reward) {
  if (!wheelForm) return;
  ['id', 'label', 'reward_type', 'amount', 'weight', 'color'].forEach((field) => {
    if (wheelForm.elements[field]) {
      wheelForm.elements[field].value = reward[field] ?? '';
    }
  });
}

if (wheelForm) {
  wheelForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    try {
      const payload = adminPayloadFromForm(wheelForm);
      if (payload.amount !== undefined) payload.amount = parseInt(payload.amount, 10);
      if (payload.weight !== undefined) payload.weight = parseFloat(payload.weight);
      await adminRequest('POST', '/admin/api/wheel-rewards', payload);
      clearForm(wheelForm);
      await loadOverview(true);
      setStatus('Wheel slice saved.');
    } catch (err) {
      setStatus(err.message, true);
    }
  });
}

function renderShop(items) {
  if (!shopListEl) return;
  shopListEl.innerHTML = '';
  items.forEach((item) => {
    const pill = document.createElement('div');
    pill.className = 'pill';
    pill.innerHTML = `
      <div class="meta">
        <strong>${item.name}</strong>
        <span>${item.stars}⭐ • ${item.energy}⚡ • Bonus spins ${item.bonus_spins}</span>
      </div>
      <div class="actions">
        <button data-action="edit">Edit</button>
        <button data-action="toggle">${item.is_active ? 'Disable' : 'Enable'}</button>
      </div>
    `;
    pill.querySelector('[data-action="edit"]').addEventListener('click', () => fillShopForm(item));
    pill.querySelector('[data-action="toggle"]').addEventListener('click', async () => {
      try {
        await adminRequest('POST', '/admin/api/shop-items', { id: item.id, is_active: !item.is_active });
        await loadOverview(true);
        setStatus(`Bundle ${item.is_active ? 'disabled' : 'enabled'}.`);
      } catch (err) {
        setStatus(err.message, true);
      }
    });
    shopListEl.appendChild(pill);
  });
}

function fillShopForm(item) {
  if (!shopForm) return;
  ['id', 'name', 'slug', 'stars', 'energy', 'bonus_spins', 'description', 'art_url', 'sort_order'].forEach((field) => {
    if (shopForm.elements[field]) {
      shopForm.elements[field].value = item[field] ?? '';
    }
  });
  if (shopForm.elements.is_active) {
    shopForm.elements.is_active.checked = !!item.is_active;
  }
}

if (shopForm) {
  shopForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    try {
      const payload = adminPayloadFromForm(shopForm);
      ['stars', 'energy', 'bonus_spins', 'sort_order'].forEach((key) => {
        if (payload[key] !== undefined) payload[key] = parseInt(payload[key], 10);
      });
      await adminRequest('POST', '/admin/api/shop-items', payload);
      clearForm(shopForm);
      await loadOverview(true);
      setStatus('Shop bundle saved.');
    } catch (err) {
      setStatus(err.message, true);
    }
  });
}

function renderEvents(events) {
  if (!eventsListEl) return;
  eventsListEl.innerHTML = '';
  events.forEach((event) => {
    const pill = document.createElement('div');
    pill.className = 'pill';
    pill.innerHTML = `
      <div class="meta">
        <strong>${event.name}</strong>
        <span>${event.event_type.toUpperCase()} • ${new Date(event.start_at).toLocaleDateString()} → ${new Date(event.end_at).toLocaleDateString()}</span>
      </div>
      <div class="actions">
        <button data-action="edit">Edit</button>
        <button data-action="delete">Delete</button>
      </div>
    `;
    pill.querySelector('[data-action="edit"]').addEventListener('click', () => fillEventForm(event));
    pill.querySelector('[data-action="delete"]').addEventListener('click', async () => {
      try {
        await adminRequest('DELETE', `/admin/api/events/${event.id}`);
        await loadOverview(true);
        setStatus('Event removed.');
      } catch (err) {
        setStatus(err.message, true);
      }
    });
    eventsListEl.appendChild(pill);
  });
}

function fillEventForm(event) {
  if (!eventForm) return;
  ['id', 'name', 'slug', 'event_type', 'target_spins', 'reward_type', 'reward_amount', 'banner_url', 'description'].forEach((field) => {
    if (eventForm.elements[field]) {
      eventForm.elements[field].value = event[field] ?? '';
    }
  });
  if (eventForm.elements.start_at && event.start_at) {
    eventForm.elements.start_at.value = event.start_at.slice(0, 16);
  }
  if (eventForm.elements.end_at && event.end_at) {
    eventForm.elements.end_at.value = event.end_at.slice(0, 16);
  }
}

if (eventForm) {
  eventForm.addEventListener('submit', async (evt) => {
    evt.preventDefault();
    try {
      const payload = adminPayloadFromForm(eventForm);
      ['target_spins', 'reward_amount'].forEach((key) => {
        if (payload[key] !== undefined) payload[key] = parseInt(payload[key], 10);
      });
      if (payload.start_at) payload.start_at = new Date(payload.start_at).toISOString();
      if (payload.end_at) payload.end_at = new Date(payload.end_at).toISOString();
      await adminRequest('POST', '/admin/api/events', payload);
      clearForm(eventForm);
      await loadOverview(true);
      setStatus('Event saved.');
    } catch (err) {
      setStatus(err.message, true);
    }
  });
}

if (rewardLinkForm) {
  rewardLinkForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    try {
      const payload = adminPayloadFromForm(rewardLinkForm);
      payload.amount = parseInt(payload.amount, 10);
      payload.uses = parseInt(payload.uses, 10);
      const data = await adminRequest('POST', '/admin/api/reward-links', payload);
      rewardLinkResult.textContent = `Created: ${data.reward_url}`;
      rewardLinkResult.style.color = '#4ade80';
      await loadOverview(true);
    } catch (err) {
      rewardLinkResult.textContent = err.message;
      rewardLinkResult.style.color = '#f87171';
    }
  });
}

if (broadcastForm) {
  broadcastForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    try {
      const payload = adminPayloadFromForm(broadcastForm);
      await adminRequest('POST', '/admin/api/broadcasts', payload);
      clearForm(broadcastForm);
      await loadOverview(true);
      setStatus('Broadcast recorded.');
    } catch (err) {
      setStatus(err.message, true);
    }
  });
}

function renderRewardHistory(links, broadcasts) {
  if (rewardLinkList) {
    rewardLinkList.innerHTML = '';
    links.forEach((link) => {
      const li = document.createElement('li');
      li.innerHTML = `<strong>${link.title || link.reward_type}</strong><span>${link.amount} • Uses left ${link.uses_left}</span><a href="${location.origin}/redeem/${link.token}" target="_blank">Open</a>`;
      rewardLinkList.appendChild(li);
    });
  }
  if (broadcastList) {
    broadcastList.innerHTML = '';
    broadcasts.forEach((cast) => {
      const li = document.createElement('li');
      li.innerHTML = `<strong>${cast.title}</strong><span>${cast.body}</span>${cast.reward_url ? `<a href="${cast.reward_url}" target="_blank">Reward</a>` : ''}`;
      broadcastList.appendChild(li);
    });
  }
}

function renderLeaderboardPreview(entries) {
  if (!leaderboardPreview) return;
  leaderboardPreview.innerHTML = '';
  entries.forEach((entry, index) => {
    const pill = document.createElement('div');
    pill.className = 'pill';
    pill.innerHTML = `<div class="meta"><strong>#${index + 1} ${entry.username}</strong><span>${entry.weekly_coins} SharkCoins • Level ${entry.level}</span></div>`;
    leaderboardPreview.appendChild(pill);
  });
}

if (leaderboardRewardForm) {
  leaderboardRewardForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    try {
      const payload = adminPayloadFromForm(leaderboardRewardForm);
      payload.top_n = parseInt(payload.top_n, 10) || 0;
      payload.amount = parseInt(payload.amount, 10) || 0;
      await adminRequest('POST', '/admin/api/leaderboard/reward', payload);
      setStatus('Leaderboard reward granted.');
      await loadOverview(true);
    } catch (err) {
      setStatus(err.message, true);
    }
  });
}

if (resetLeaderboardBtn) {
  resetLeaderboardBtn.addEventListener('click', async () => {
    if (!confirm('Reset weekly SharkCoins for all users?')) return;
    try {
      await adminRequest('POST', '/admin/api/leaderboard/reset', {});
      setStatus('Weekly scores reset.');
      await loadOverview(true);
    } catch (err) {
      setStatus(err.message, true);
    }
  });
}

if (loadBtn) {
  loadBtn.addEventListener('click', () => loadOverview(false));
}

// Attempt to auto-load if a secret was previously stored
const savedSecret = sessionStorage.getItem('sharkspin-admin-secret');
if (savedSecret) {
  secretInput.value = savedSecret;
  adminState.secret = savedSecret;
  loadOverview(true);
}

if (secretInput) {
  secretInput.addEventListener('change', () => {
    sessionStorage.setItem('sharkspin-admin-secret', secretInput.value.trim());
  });
}
