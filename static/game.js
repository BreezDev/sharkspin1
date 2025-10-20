const tg = window.Telegram?.WebApp;
const state = {
  token: null,
  multiplier: 1,
  wheelRewards: [],
  wheelRotation: 0,
};

async function postJSON(url, data) {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return await res.json();
}

async function getJSON(url) {
  const res = await fetch(url);
  return await res.json();
}

function updateStats(payload) {
  if (!payload) return;
  if (payload.coins !== undefined) {
    document.getElementById('coins').textContent = payload.coins;
  }
  if (payload.energy !== undefined) {
    document.getElementById('energy').textContent = payload.energy;
  }
  if (payload.level !== undefined) {
    document.getElementById('level').textContent = payload.level;
  }
  if (payload.wheel_tokens !== undefined) {
    document.getElementById('wheelTokens').textContent = payload.wheel_tokens;
  }
}

function animateReels(finalSymbols) {
  const reels = [document.getElementById('reel1'), document.getElementById('reel2'), document.getElementById('reel3')];
  const interimSymbols = ['🦈', '💎', '🍋', '🎲', '🔱', '🪙'];
  reels.forEach((reel, idx) => {
    reel.classList.add('spinning');
    let tick = 0;
    const spinLoop = setInterval(() => {
      reel.textContent = interimSymbols[(tick + idx) % interimSymbols.length];
      tick += 1;
    }, 75);
    setTimeout(() => {
      clearInterval(spinLoop);
      reel.textContent = finalSymbols[idx];
      reel.classList.remove('spinning');
    }, 800 + idx * 120);
  });
}

async function auth() {
  const user = tg?.initDataUnsafe?.user;
  const tg_user_id = user?.id?.toString() || prompt('Enter Test TG ID');
  const username = user?.username || 'webapp_user';
  const resp = await postJSON('/api/auth', { tg_user_id, username });
  if (resp.ok) {
    state.token = resp.token;
    updateStats(resp);
    await Promise.all([loadWheelRewards(), loadEvents(), loadAlbums()]);
  } else {
    document.getElementById('result').textContent = resp.error || 'Authentication failed';
  }
}

async function refreshState() {
  if (!state.token) return;
  const res = await getJSON(`/api/me?token=${encodeURIComponent(state.token)}`);
  if (res.ok) {
    updateStats(res);
  }
}

async function spin() {
  if (!state.token) return;
  document.getElementById('result').textContent = 'Spinning...';
  const res = await postJSON('/api/spin', {
    token: state.token,
    multiplier: state.multiplier,
  });
  if (!res.ok) {
    document.getElementById('result').textContent = res.error || 'Unable to spin right now.';
    return;
  }
  updateStats(res);
  if (res.result?.symbols) {
    animateReels(res.result.symbols);
  }
  const label = res.result?.label ? ` (${res.result.label})` : '';
  document.getElementById('result').textContent = `+${res.payout} SharkCoins${label}`;
  setTimeout(refreshState, 1200);
  await Promise.all([loadEvents(true)]);
}

function renderWheel(rewards) {
  const wheel = document.getElementById('fortuneWheel');
  if (!wheel) return;
  wheel.innerHTML = '';
  if (!rewards || !rewards.length) {
    wheel.textContent = 'No rewards configured yet';
    return;
  }
  const slice = 360 / rewards.length;
  rewards.forEach((reward, index) => {
    const segment = document.createElement('div');
    segment.className = 'wheel-segment';
    segment.style.background = reward.color || '#02f2ff';
    segment.style.transform = `rotate(${index * slice}deg) skewY(${90 - slice}deg)`;
    const label = document.createElement('span');
    label.textContent = reward.label;
    label.style.transform = `skewY(${-(90 - slice)}deg) rotate(${slice / 2}deg)`;
    segment.appendChild(label);
    wheel.appendChild(segment);
  });
  state.wheelRewards = rewards;
}

async function loadWheelRewards() {
  if (!state.token) return;
  const res = await getJSON(`/api/wheel?token=${encodeURIComponent(state.token)}`);
  if (res.ok) {
    renderWheel(res.rewards || []);
    updateStats(res);
  }
}

async function spinWheel() {
  if (!state.token) return;
  const wheel = document.getElementById('fortuneWheel');
  document.getElementById('wheelMessage').textContent = 'Wheel is spinning...';
  wheel.classList.add('rotating');
  const res = await postJSON('/api/wheel/spin', { token: state.token });
  setTimeout(() => wheel.classList.remove('rotating'), 2200);
  if (!res.ok) {
    document.getElementById('wheelMessage').textContent = res.error || 'No spins left.';
    return;
  }
  updateStats(res);
  const reward = res.reward;
  document.getElementById('wheelMessage').textContent = `Wheel Reward: ${reward.label}`;
  await Promise.all([loadAlbums(true), loadEvents(true)]);
}

function renderEvents(events = []) {
  const container = document.getElementById('eventsList');
  if (!container) return;
  container.innerHTML = '';
  if (!events.length) {
    container.innerHTML = '<p>No live events yet. Check back soon!</p>';
    return;
  }
  events.forEach((event) => {
    const card = document.createElement('div');
    card.className = 'event-card';
    const progressPct = Math.min(100, Math.round((event.progress / event.target_spins) * 100));
    card.innerHTML = `
      <div class="status">${event.status.toUpperCase()}</div>
      <h3>${event.name}</h3>
      <p>${event.description}</p>
      <p>Reward: ${event.reward_amount} ${event.reward_type}</p>
      <progress value="${event.progress}" max="${event.target_spins}"></progress>
      <div>${progressPct}% complete</div>
    `;
    container.appendChild(card);
  });
}

async function loadEvents(skipStats) {
  if (!state.token) return;
  const res = await getJSON(`/api/events?token=${encodeURIComponent(state.token)}`);
  if (res.ok) {
    if (!skipStats) updateStats(res);
    renderEvents(res.events || []);
  }
}

function renderAlbums(albums = []) {
  const container = document.getElementById('albumsList');
  if (!container) return;
  container.innerHTML = '';
  if (!albums.length) {
    container.innerHTML = '<p>Sticker albums unlock soon!</p>';
    return;
  }
  albums.forEach((album) => {
    const card = document.createElement('div');
    card.className = 'album-card';
    const progressPct = Math.round((album.owned_count / album.total) * 100);
    const rewardTag = album.reward_claimed ? '<span class="claimed">Reward claimed</span>' : `<span>${album.reward_spins} bonus spins</span>`;
    const stickerTiles = album.stickers
      .map((sticker) => `
        <div class="sticker-tile">
          <div>${sticker.name}</div>
          <span class="qty">x${sticker.quantity}</span>
        </div>
      `)
      .join('');
    card.innerHTML = `
      <header>
        <div>
          <h3>${album.name}</h3>
          <small>${album.description}</small>
        </div>
        ${rewardTag}
      </header>
      <div class="stickers-grid">${stickerTiles}</div>
      <div class="album-actions">
        <span>${progressPct}% collected</span>
        <button class="secondary" data-album="${album.id}">Open Pack (${album.sticker_cost}🪙)</button>
      </div>
    `;
    container.appendChild(card);
  });
}

async function loadAlbums(skipStats) {
  if (!state.token) return;
  const res = await getJSON(`/api/stickers?token=${encodeURIComponent(state.token)}`);
  if (res.ok) {
    if (!skipStats) updateStats(res);
    renderAlbums(res.albums || []);
  }
}

async function openSticker(albumId) {
  if (!state.token) return;
  const res = await postJSON('/api/stickers/open', {
    token: state.token,
    album_id: albumId,
  });
  if (!res.ok) {
    alert(res.error || 'Unable to open sticker pack');
    return;
  }
  updateStats(res);
  const sticker = res.sticker;
  let message = `You found ${sticker.name} (${sticker.rarity})`;
  if (res.album_rewarded) {
    message += '\nAlbum completed! Spins have been added to your balance.';
  }
  alert(message);
  await loadAlbums(true);
}

function bindEvents() {
  document.getElementById('spinBtn')?.addEventListener('click', spin);
  document.getElementById('wheelSpinBtn')?.addEventListener('click', spinWheel);
  document.getElementById('buyEnergyBtn')?.addEventListener('click', buyEnergy);
  document.querySelectorAll('.multiplier-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      state.multiplier = parseInt(btn.dataset.mult, 10);
      document.querySelectorAll('.multiplier-btn').forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
    });
  });
  document.getElementById('albumsList')?.addEventListener('click', (ev) => {
    const target = ev.target.closest('button[data-album]');
    if (!target) return;
    const albumId = parseInt(target.dataset.album, 10);
    openSticker(albumId);
  });
}

function buyEnergy() {
  const botUsername = tg?.initDataUnsafe?.receiver?.username || 'YOUR_BOT_USERNAME';
  const url = `https://t.me/${botUsername}?start=buy`;
  if (tg?.openTelegramLink) {
    tg.openTelegramLink(url);
  } else {
    window.open(url, '_blank');
  }
}

window.addEventListener('DOMContentLoaded', () => {
  bindEvents();
  auth();
  if (tg) {
    tg.expand();
  }

  const userId = tg?.initDataUnsafe?.user?.id;
  const startParam = tg?.initDataUnsafe?.start_param;
  if (startParam && startParam.startsWith('redeem_')) {
    const token = startParam.replace('redeem_', '');
    if (!userId) {
      alert('You must open this link inside Telegram to claim rewards.');
    } else {
      fetch(`/redeem/${token}?tg_user_id=${userId}`)
        .then((r) => r.text())
        .then((html) => {
          document.body.innerHTML = html;
        });
    }
  }
});
