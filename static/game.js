const tg = window.Telegram?.WebApp;

const state = {
  token: null,
  multiplier: 1,
  energyPerSpin: 1,
  energy: 0,
  coins: 0,
  coinCostPerSpin: 0,
  wheelRewards: [],
  wheelRotation: 0,
  daily: null,
  packages: [],
  taskbar: [],
  leaderboard: [],
  spinMultipliers: [],
};

const SLOT_SYMBOLS = ['🪙', '⚡', '🌀', '💠', '🦈', '🎁'];
const DEFAULT_MULTIPLIERS = [
  1,
  5,
  10,
  25,
  50,
  100,
  150,
  250,
  500,
  700,
  1000,
  2000,
  5000,
  10000,
  20000,
  50000,
  100000,
];

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

function switchView(view) {
  document.querySelectorAll('.view').forEach((section) => {
    section.classList.toggle('active', section.dataset.view === view);
  });
  document.querySelectorAll('.taskbar button').forEach((btn) => {
    btn.classList.toggle('active', btn.dataset.view === view);
  });
}

function setupTaskbar(links = []) {
  const bar = document.getElementById('taskbar');
  bar.innerHTML = '';
  const defaultLink = links.find((link) => link.default) || links[0];
  links.forEach((link) => {
    const button = document.createElement('button');
    button.dataset.view = link.target;
    button.innerHTML = `${link.emoji || ''} ${link.label}`;
    button.addEventListener('click', () => switchView(link.target));
    if (defaultLink && link.target === defaultLink.target) {
      button.classList.add('active');
    }
    bar.appendChild(button);
  });
  if (defaultLink) {
    switchView(defaultLink.target);
  }
}

function renderLevelProgress(progress) {
  if (!progress) return;
  const pct = Math.min(100, progress.percent || 0);
  const progressEl = document.getElementById('levelProgress');
  const detail = document.getElementById('progressDetail');
  if (progressEl) progressEl.value = pct;
  if (detail) {
    const floor = progress.floor ?? 0;
    const ceiling = progress.ceiling ?? 0;
    const current = progress.current_xp ?? 0;
    detail.textContent = `${Math.max(current - floor, 0)} / ${Math.max(ceiling - floor, 1)} XP`;
  }
}

function selectMultiplier(value) {
  state.multiplier = value;
  document.querySelectorAll('.multiplier-buttons .chip').forEach((btn) => {
    btn.classList.toggle('active', parseInt(btn.dataset.mult, 10) === value);
  });
  updateWagerDisplay();
}

function renderMultiplierButtons(options = state.spinMultipliers) {
  const container = document.querySelector('.multiplier-buttons');
  if (!container) return;
  container.innerHTML = '';
  const values = options && options.length ? options : DEFAULT_MULTIPLIERS;
  values.forEach((value) => {
    const button = document.createElement('button');
    button.className = 'chip';
    button.dataset.mult = value;
    button.textContent = `x${value}`;
    if (value === state.multiplier) button.classList.add('active');
    button.addEventListener('click', () => {
      if (button.disabled) return;
      selectMultiplier(value);
    });
    container.appendChild(button);
  });
  updateMultiplierButtons(state.energy, state.coins);
}

function updateMultiplierButtons(currentEnergy = state.energy, currentCoins = state.coins) {
  const energyCost = state.energyPerSpin || 1;
  const coinCost = state.coinCostPerSpin || 0;
  document.querySelectorAll('.multiplier-buttons .chip').forEach((btn) => {
    const mult = parseInt(btn.dataset.mult, 10);
    const affordable =
      currentEnergy >= mult * energyCost && (coinCost === 0 || currentCoins >= mult * coinCost);
    btn.disabled = !affordable;
    if (mult === state.multiplier && !affordable) {
      selectMultiplier(1);
    }
  });
  updateWagerDisplay();
}

function updateWagerDisplay() {
  const energyEl = document.getElementById('wagerEnergy');
  const coinEl = document.getElementById('wagerCoins');
  const energyCost = (state.energyPerSpin || 1) * state.multiplier;
  const coinCost = (state.coinCostPerSpin || 0) * state.multiplier;
  if (energyEl) {
    energyEl.textContent = `${energyCost.toLocaleString()}⚡`;
  }
  if (coinEl) {
    coinEl.textContent = `${coinCost.toLocaleString()}🪙`;
  }
  const spinBtn = document.getElementById('spinBtn');
  if (spinBtn) {
    const hasEnergy = state.energy >= energyCost;
    const hasCoins = coinCost === 0 || state.coins >= coinCost;
    spinBtn.disabled = !(hasEnergy && hasCoins);
  }
}

function updateStats(payload) {
  if (!payload) return;
  if (payload.coins !== undefined) {
    document.getElementById('coins').textContent = payload.coins;
    state.coins = payload.coins;
    updateMultiplierButtons(state.energy, payload.coins);
  }
  if (payload.energy !== undefined) {
    document.getElementById('energy').textContent = payload.energy;
    state.energy = payload.energy;
    updateMultiplierButtons(payload.energy, state.coins);
  }
  if (payload.level !== undefined) document.getElementById('level').textContent = payload.level;
  if (payload.wheel_tokens !== undefined) document.getElementById('wheelTokens').textContent = payload.wheel_tokens;
  if (payload.weekly_coins !== undefined) document.getElementById('weeklyCoins').textContent = payload.weekly_coins;
  if (payload.energy_per_spin !== undefined) state.energyPerSpin = payload.energy_per_spin;
  if (payload.coin_cost_per_spin !== undefined) state.coinCostPerSpin = payload.coin_cost_per_spin;
  if (Array.isArray(payload.spin_multipliers) && payload.spin_multipliers.length) {
    state.spinMultipliers = payload.spin_multipliers.map((value) => parseInt(value, 10)).filter(Boolean);
    renderMultiplierButtons();
  } else {
    updateWagerDisplay();
  }
  if (payload.progress) renderLevelProgress(payload.progress);
  if (payload.daily) renderDaily(payload.daily);
}

function animateReels(finalSymbols) {
  const reels = [document.getElementById('reel1'), document.getElementById('reel2'), document.getElementById('reel3')];
  reels.forEach((reel, idx) => {
    reel.classList.add('spinning');
    let tick = 0;
    const spinLoop = setInterval(() => {
      reel.textContent = SLOT_SYMBOLS[(tick + idx) % SLOT_SYMBOLS.length];
      tick += 1;
    }, 70);
    setTimeout(() => {
      clearInterval(spinLoop);
      reel.textContent = finalSymbols[idx];
      reel.classList.remove('spinning');
    }, 820 + idx * 130);
  });
}

function formatRewards(rewards = {}) {
  const parts = [];
  if (rewards.coins) parts.push(`+${rewards.coins}🪙`);
  if (rewards.energy) parts.push(`+${rewards.energy}⚡`);
  if (rewards.wheel_tokens) parts.push(`+${rewards.wheel_tokens}🌀`);
  return parts.length ? parts.join(' • ') : 'No reward';
}

async function auth() {
  const user = tg?.initDataUnsafe?.user;
  const tg_user_id = user?.id?.toString() || prompt('Enter Test TG ID');
  const username = user?.username || 'webapp_user';
  const resp = await postJSON('/api/auth', { tg_user_id, username });
  if (!resp.ok) {
    document.getElementById('result').textContent = resp.error || 'Authentication failed';
    return;
  }
  state.token = resp.token;
  state.energyPerSpin = resp.energy_per_spin || state.energyPerSpin;
  state.coinCostPerSpin = resp.coin_cost_per_spin ?? state.coinCostPerSpin;
  if (Array.isArray(resp.spin_multipliers) && resp.spin_multipliers.length) {
    state.spinMultipliers = resp.spin_multipliers.map((value) => parseInt(value, 10)).filter(Boolean);
  }
  renderMultiplierButtons();
  updateStats(resp);
  await Promise.all([
    loadCatalog(),
    loadWheelRewards(),
    loadEvents(),
    loadAlbums(),
    loadLeaderboard(),
    loadDaily(true),
    loadShop(true),
  ]);
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
  if (res.result?.symbols) animateReels(res.result.symbols);
  const rewardText = formatRewards(res.result?.rewards);
  const label = res.result?.label ? ` (${res.result.label})` : '';
  const hasCoinCost = typeof res.result?.coin_cost === 'number';
  const wagerCoin = hasCoinCost ? `Wager ${res.result.coin_cost.toLocaleString()}🪙` : '';
  const hasEnergySpend = typeof res.result?.energy_spent === 'number';
  const energySpent = hasEnergySpend ? `Spent ${res.result.energy_spent.toLocaleString()}⚡` : '';
  const net = typeof res.result?.net_coins === 'number'
    ? `Net ${res.result.net_coins >= 0 ? '+' : ''}${res.result.net_coins.toLocaleString()}🪙`
    : '';
  const messageBits = [wagerCoin, energySpent, rewardText, net].filter(Boolean);
  document.getElementById('result').textContent = `${messageBits.join(' • ')}${label}`;
  setTimeout(refreshState, 1500);
  await loadEvents(true);
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
  setTimeout(() => wheel.classList.remove('rotating'), 2400);
  if (!res.ok) {
    document.getElementById('wheelMessage').textContent = res.error || 'No spins left.';
    return;
  }
  updateStats(res);
  const reward = res.reward;
  document.getElementById('wheelMessage').textContent = `${reward.label} awarded!`;
  await Promise.all([loadAlbums(true), loadEvents(true)]);
}

function renderEvents(events = []) {
  const container = document.getElementById('eventsList');
  if (!container) return;
  container.innerHTML = '';
  if (!events.length) {
    container.innerHTML = '<p>No live events yet. Check back soon!</p>';
  }
  events.forEach((event) => {
    const card = document.createElement('div');
    card.className = 'event-card';
    if (event.banner_url) {
      card.style.backgroundImage = `url(${event.banner_url})`;
      card.style.backgroundSize = 'cover';
      card.style.backgroundPosition = 'center';
      card.style.color = '#f8fafc';
    }
    const progressValue = Math.min(event.progress ?? 0, event.target_spins || 1);
    const progressPct = Math.min(100, Math.round((progressValue / Math.max(event.target_spins || 1, 1)) * 100));
    card.innerHTML = `
      <div class="status">${event.event_type?.toUpperCase() || 'LIVE'} • ${event.status.toUpperCase()}</div>
      <h3>${event.name}</h3>
      <p>${event.description}</p>
      <div class="reward">Reward: ${event.reward_amount} ${event.reward_type}</div>
      <progress value="${progressValue}" max="${event.target_spins}"></progress>
      <div class="progress-line">${progressPct}% • ${progressValue}/${event.target_spins} spins</div>
    `;
    container.appendChild(card);
  });
  renderSeasonalEvents(events);
  renderEventsBoard(events);
}

function eventArt(type) {
  const artMap = {
    live: '/static/images/seasonal-energy.svg',
    seasonal: '/static/images/seasonal-wheel.svg',
    limited: '/static/images/seasonal-sticker.svg',
  };
  return artMap[type] || artMap.live;
}

function renderSeasonalEvents(events = []) {
  const container = document.getElementById('seasonalEvents');
  if (!container) return;
  container.innerHTML = '';
  const featured = events.slice(0, 3);
  if (!featured.length) {
    container.innerHTML = '<p>Spin to unlock seasonal showcases.</p>';
    return;
  }
  featured.forEach((event) => {
    const card = document.createElement('div');
    card.className = 'seasonal-card';
    card.innerHTML = `
      <span class="tag">${event.event_type || 'live'}</span>
      <h3>${event.name}</h3>
      <p>${event.description}</p>
      <button class="cta">Jump In →</button>
    `;
    const art = document.createElement('img');
    art.src = event.banner_url || eventArt(event.event_type);
    art.alt = event.name;
    card.appendChild(art);
    container.appendChild(card);
  });
}

function renderEventsBoard(events = []) {
  const board = document.getElementById('eventsBoard');
  if (!board) return;
  board.innerHTML = '';
  if (!events.length) {
    board.innerHTML = '<p>No scheduled events. Admins can launch tournaments from the dashboard.</p>';
    return;
  }
  events.forEach((event) => {
    const sheet = document.createElement('div');
    sheet.className = 'event-sheet';
    const startDate = new Date(event.start_at).toLocaleString();
    const endDate = new Date(event.end_at).toLocaleString();
    const progressValue = Math.min(event.progress ?? 0, event.target_spins || 1);
    const progressPct = Math.min(100, Math.round((progressValue / Math.max(event.target_spins || 1, 1)) * 100));
    sheet.innerHTML = `
      <header>
        <div>
          <h3>${event.name}</h3>
          <small>${startDate} → ${endDate}</small>
        </div>
        <span class="badge">${event.status.toUpperCase()}</span>
      </header>
      <p>${event.description}</p>
      <div>Reward: ${event.reward_amount} ${event.reward_type}</div>
      <progress value="${progressValue}" max="${event.target_spins}"></progress>
      <div>${progressPct}% complete • ${progressValue}/${event.target_spins} spins</div>
    `;
    board.appendChild(sheet);
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

async function loadLeaderboard() {
  if (!state.token) return;
  const res = await getJSON(`/api/leaderboard?token=${encodeURIComponent(state.token)}`);
  if (res.ok) {
    renderLeaderboard(res.leaders || [], res.me || null);
  }
}

function renderLeaderboard(leaders = [], me = null) {
  const list = document.getElementById('leaderboardList');
  const meBox = document.getElementById('leaderboardMe');
  if (list) {
    list.innerHTML = '';
    if (!leaders.length) {
      const empty = document.createElement('li');
      empty.textContent = 'No leaderboard entries yet. Spin to earn SharkCoins!';
      list.appendChild(empty);
    } else {
      leaders.forEach((leader) => {
        const item = document.createElement('li');
        item.innerHTML = `
          <div>
            <strong>#${leader.position} ${leader.username}</strong>
            <small>Level ${leader.level}</small>
          </div>
          <div>${leader.weekly_coins}🪙</div>
        `;
        list.appendChild(item);
      });
    }
  }
  if (meBox) {
    if (!me) {
      meBox.textContent = 'Earn SharkCoins this week to place on the leaderboard.';
    } else {
      const place = me.position ? `#${me.position}` : 'Unranked';
      meBox.innerHTML = `<span>${place}</span><span>${me.weekly_coins}🪙 this week</span>`;
    }
  }
  state.leaderboard = leaders;
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

function renderDaily(daily) {
  state.daily = daily;
  const summary = document.getElementById('dailySummary');
  const details = document.getElementById('dailyDetails');
  const button = document.getElementById('claimDailyBtn');
  if (!daily) {
    summary.textContent = 'Daily rewards will unlock soon.';
    details.textContent = '';
    button.disabled = true;
    return;
  }
  const reward = daily.next_reward || {};
  summary.textContent = daily.can_claim
    ? `Streak ${daily.streak || 0}. Claim now for ${reward.coins || 0}🪙, ${reward.energy || 0}⚡.`
    : `Next reward in ${formatCountdown(daily.seconds_until)}.`;
  details.textContent = `Next bonus: ${reward.coins || 0}🪙 • ${reward.energy || 0}⚡${reward.wheel_tokens ? ` • +${reward.wheel_tokens}🌀` : ''}`;
  button.disabled = !daily.can_claim;
  button.textContent = daily.can_claim ? 'Claim Reward' : 'Cooldown';
}

function formatCountdown(seconds = 0) {
  const hrs = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  return `${hrs.toString().padStart(2, '0')}h ${mins.toString().padStart(2, '0')}m`;
}

async function loadDaily(skipStats) {
  if (!state.token) return;
  const res = await getJSON(`/api/daily?token=${encodeURIComponent(state.token)}`);
  if (res.ok) {
    if (!skipStats) updateStats(res);
    else if (res.daily) renderDaily(res.daily);
  }
}

async function claimDaily() {
  if (!state.token) return;
  const res = await postJSON('/api/daily/claim', { token: state.token });
  if (!res.ok) {
    alert(res.error || 'Daily reward unavailable.');
    if (res.daily) renderDaily(res.daily);
    return;
  }
  updateStats(res);
  const reward = res.reward || {};
  alert(`Reward claimed! +${reward.coins || 0}🪙, +${reward.energy || 0}⚡${reward.wheel_tokens ? `, +${reward.wheel_tokens}🌀` : ''}`);
}

function renderShop(packages = []) {
  const container = document.getElementById('shopList');
  if (!container) return;
  container.innerHTML = '';
  if (!packages.length) {
    container.innerHTML = '<p>No packages configured. Update Config.STAR_PACKAGES.</p>';
    return;
  }
  packages.forEach((pack) => {
    const card = document.createElement('div');
    card.className = 'shop-card';
    card.innerHTML = `
      <header>
        <img src="${pack.art_url || '/static/images/star-pack-coral.svg'}" alt="${pack.name}" />
        <div>
          <h3>${pack.name}</h3>
          <div class="shop-meta"><span class="stars">${pack.stars}⭐</span> <span>${pack.energy}⚡</span> <span>${pack.bonus_spins}🌀</span></div>
        </div>
      </header>
      <p>${pack.description || ''}</p>
      <button class="primary" data-pack="${pack.id}">Purchase in-app</button>
    `;
    container.appendChild(card);
  });
  state.packages = packages;
}

async function loadShop(skipStats) {
  if (!state.token) return;
  const res = await getJSON(`/api/shop?token=${encodeURIComponent(state.token)}`);
  if (res.ok) {
    if (!skipStats) updateStats(res);
    renderShop(res.packages || []);
  }
}

async function orderPackage(packageId) {
  if (!state.token) return;
  const res = await postJSON('/api/shop/order', {
    token: state.token,
    package_id: packageId,
  });
  if (!res.ok) {
    alert(res.error || 'Unable to create invoice.');
    return;
  }
  if (res.invoice_url && tg?.openInvoice) {
    tg.openInvoice(res.invoice_url, (status) => {
      if (status === 'paid') {
        alert('Payment successful!');
        refreshState();
      } else if (status === 'failed') {
        alert('Payment failed or cancelled.');
      }
    });
    return;
  }
  if (res.fallback_url && tg?.openTelegramLink) {
    tg.openTelegramLink(res.fallback_url);
    return;
  }
  alert(res.warning || 'Invoice link unavailable. Please try /buy in the bot as fallback.');
}

function renderCallouts(callouts = []) {
  const container = document.getElementById('calloutsGrid');
  if (!container) return;
  container.innerHTML = '';
  callouts.forEach((item) => {
    const card = document.createElement('div');
    card.className = 'callout';
    card.innerHTML = `
      <img src="${item.icon}" alt="${item.title}" />
      <div>
        <h3>${item.title}</h3>
        <p>${item.body}</p>
      </div>
    `;
    container.appendChild(card);
  });
}

function renderGuideSections(sections = []) {
  const container = document.getElementById('guideSections');
  if (!container) return;
  container.innerHTML = '';
  sections.forEach((section) => {
    const card = document.createElement('div');
    card.className = 'guide-card';
    const entries = (section.entries || [])
      .map(
        (entry) => `
        <dt>${entry.heading}</dt>
        <dd>${entry.description}</dd>
      `,
      )
      .join('');
    card.innerHTML = `
      <h3>${section.title}</h3>
      <dl>${entries}</dl>
    `;
    container.appendChild(card);
  });
}

async function loadCatalog() {
  if (!state.token) return;
  const res = await getJSON(`/api/catalog?token=${encodeURIComponent(state.token)}`);
  if (res.ok) {
    updateStats(res);
    if (res.callouts) renderCallouts(res.callouts);
    if (res.guide) renderGuideSections(res.guide);
    if (res.taskbar) {
      state.taskbar = res.taskbar;
      setupTaskbar(res.taskbar);
    }
  }
}

function bindEvents() {
  document.getElementById('spinBtn')?.addEventListener('click', spin);
  document.getElementById('wheelSpinBtn')?.addEventListener('click', spinWheel);
  document.getElementById('claimDailyBtn')?.addEventListener('click', claimDaily);
  document.getElementById('openHelpBtn')?.addEventListener('click', () => switchView('help'));
  document.getElementById('albumsList')?.addEventListener('click', (ev) => {
    const target = ev.target.closest('button[data-album]');
    if (!target) return;
    const albumId = parseInt(target.dataset.album, 10);
    openSticker(albumId);
  });
  document.getElementById('shopList')?.addEventListener('click', (ev) => {
    const target = ev.target.closest('button[data-pack]');
    if (!target) return;
    orderPackage(target.dataset.pack);
  });
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
