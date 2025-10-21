const tg = window.Telegram?.WebApp;

const state = {
  token: null,
  multiplier: 1,
  wheelRewards: [],
  wheelRotation: -15,
  dailyInterval: null,
  activeNav: '#mainSlotSection',
};

const REWARD_META = {
  coins: { emoji: '🪙', label: 'SharkCoins', icon: '/static/images/icon-coins.svg' },
  energy: { emoji: '⚡', label: 'Energy', icon: '/static/images/icon-energy.svg' },
  wheel_tokens: { emoji: '🌀', label: 'Wheel Tokens', icon: '/static/images/icon-wheel.svg' },
  spins: { emoji: '🎰', label: 'Free Spins', icon: '/static/images/icon-spins.svg' },
  sticker_pack: { emoji: '📔', label: 'Sticker Packs', icon: '/static/images/icon-pack.svg' },
  legendary_sticker: { emoji: '🌟', label: 'Legendary Sticker', icon: '/static/images/icon-legendary.svg' },
  bonus: { emoji: '✨', label: 'Bonus', icon: '/static/images/icon-mystery.svg' },
};

function $(id) {
  return document.getElementById(id);
}

function setText(id, value) {
  const el = $(id);
  if (el !== null && value !== undefined && value !== null) {
    el.textContent = value;
  }
}

function setImage(el, src, alt) {
  if (!el) return;
  if (src) {
    el.src = src;
  }
  if (alt) {
    el.alt = alt;
  }
}

function rewardMeta(type) {
  return REWARD_META[type] || REWARD_META.bonus;
}

function highlightType(reward) {
  if (!reward) return 'bonus';
  if (reward.wheel_tokens) return 'wheel_tokens';
  if (reward.sticker_packs) return 'sticker_pack';
  if (reward.bonus_energy) return 'energy';
  if (reward.spins) return 'spins';
  if (reward.energy) return 'energy';
  return 'coins';
}

function summarizeReward(reward) {
  if (!reward) {
    return {
      title: 'Upcoming Rewards',
      text: 'Keep your streak alive to reveal more loot.',
      type: 'bonus',
    };
  }
  const chunks = [];
  if (reward.coins) chunks.push(`🪙 ${reward.coins}`);
  if (reward.energy) chunks.push(`⚡ ${reward.energy}`);
  if (reward.bonus_energy) chunks.push(`✨ +${reward.bonus_energy}⚡`);
  if (reward.wheel_tokens) chunks.push(`🌀 +${reward.wheel_tokens}`);
  if (reward.sticker_packs) chunks.push(`📔 +${reward.sticker_packs}`);
  if (reward.spins) chunks.push(`🎰 +${reward.spins}`);
  return {
    title: `Day ${reward.day} Rewards`,
    text: chunks.join(' + ') || 'Mystery reward',
    type: highlightType(reward),
  };
}

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
    setText('coins', payload.coins);
    setText('coinsStat', payload.coins);
  }
  if (payload.energy !== undefined) {
    setText('energy', payload.energy);
    setText('energyStat', payload.energy);
  }
  if (payload.wheel_tokens !== undefined) {
    setText('wheelTokens', payload.wheel_tokens);
    setText('wheelStat', payload.wheel_tokens);
  }
  if (payload.free_sticker_packs !== undefined) {
    setText('packTokens', payload.free_sticker_packs);
  }
  if (payload.level !== undefined) {
    setText('level', payload.level);
  }
  if (payload.lifetime_spins !== undefined) {
    setText('lifetimeSpins', `${payload.lifetime_spins} lifetime spins`);
  }
  if (payload.daily) {
    renderDaily(payload.daily);
    setText('dailyStreak', `${payload.daily.streak} day streak`);
  }
  if (payload.level_summary) {
    renderLevelProgress(payload.level_summary);
  }
  if (payload.trade) {
    renderTradeSummary(payload.trade);
  }
}

function renderLevelProgress(summary) {
  const progressBar = $('levelProgressBar');
  if (progressBar) {
    progressBar.style.width = `${summary.progress_pct || 0}%`;
  }
  const reward = summary.reward_preview;
  let rewardText = 'Next reward: mystery gift';
  const levelRewardIcon = $('levelRewardIcon');
  const levelRewardTitle = $('levelRewardTitle');
  const levelRewardDetail = $('levelRewardDetail');
  if (reward) {
    const meta = rewardMeta(reward.type);
    rewardText = `Next reward: ${meta.emoji} +${reward.amount} ${meta.label}`;
    if (levelRewardTitle) {
      levelRewardTitle.textContent = `${meta.emoji} Level ${summary.next_level} Reward`;
    }
    if (levelRewardDetail) {
      const friendlyType = meta.label;
      levelRewardDetail.textContent = `Reach level ${summary.next_level} to collect +${reward.amount} ${friendlyType}.`;
    }
    setImage(levelRewardIcon, meta.icon, `${meta.label} reward`);
  } else {
    if (levelRewardTitle) {
      levelRewardTitle.textContent = 'Mystery Reward Incoming';
    }
    if (levelRewardDetail) {
      levelRewardDetail.textContent = 'Keep spinning to reveal the next milestone.';
    }
    setImage(levelRewardIcon, REWARD_META.bonus.icon, 'Mystery reward');
  }
  setText('levelRewardPreview', rewardText);
  setText('levelProgressText', `${summary.progress} / ${summary.required} XP`);
}

let dailyCountdownTimer = null;

function renderDaily(daily) {
  const btn = $('claimDailyBtn');
  const timer = $('dailyTimer');
  const summaryText = $('dailySummaryText');
  const previewTitle = $('dailyPreviewTitle');
  const previewDetail = $('dailyPreviewDetail');
  const previewIcon = $('dailyPreviewIcon');
  if (!btn || !timer || !summaryText) return;

  const rewardInfo = summarizeReward(daily.reward);
  const nextInfo = summarizeReward(daily.next_reward);
  const todayLine = rewardInfo.text ? rewardInfo.text : 'Mystery treasure';
  const nextLine = nextInfo.text ? `Next: ${nextInfo.text}` : '';
  const summaryBits = [todayLine, nextLine].filter(Boolean).join(' • ');
  summaryText.textContent = `Claim ${rewardInfo.title}: ${summaryBits}. Keep streaks raging for mega loot!`;

  if (previewTitle) {
    previewTitle.textContent = rewardInfo.title;
  }
  if (previewDetail) {
    previewDetail.textContent = nextLine ? `${todayLine} • ${nextLine}` : todayLine;
  }
  const highlight = rewardMeta(rewardInfo.type);
  setImage(previewIcon, highlight.icon, rewardInfo.title);

  btn.disabled = !daily.can_claim;
  btn.textContent = daily.can_claim ? 'Claim Today’s Treasure' : 'Treasure Cooling Down';
  timer.textContent = daily.can_claim ? 'Ready now' : formatCountdown(daily.next_available_at);

  if (dailyCountdownTimer) {
    clearInterval(dailyCountdownTimer);
    dailyCountdownTimer = null;
  }

  if (!daily.can_claim && daily.next_available_at) {
    dailyCountdownTimer = setInterval(() => {
      timer.textContent = formatCountdown(daily.next_available_at);
    }, 1000);
  }

  renderDailyMilestones(daily.milestones || []);
}

function renderDailyMilestones(milestones) {
  const list = $('dailyMilestones');
  if (!list) return;
  list.innerHTML = '';
  if (!milestones.length) {
    list.innerHTML = '<li class="milestone-card">Streak milestones will appear soon.</li>';
    return;
  }
  milestones.forEach((milestone) => {
    const summary = summarizeReward(milestone);
    const type = milestone.upcoming ? summary.type : highlightType(milestone);
    const meta = rewardMeta(type);
    const li = document.createElement('li');
    li.className = 'milestone-card';
    if (milestone.achieved) li.classList.add('achieved');
    if (milestone.upcoming) li.classList.add('upcoming');
    li.innerHTML = `
      <div class="milestone-icon"><img src="${meta.icon}" alt="${meta.label}" /></div>
      <div class="milestone-copy">
        <strong>Day ${milestone.day}</strong>
        <span>${summary.text}</span>
      </div>
      <span class="milestone-status">${milestone.achieved ? 'Claimed' : milestone.upcoming ? 'Next' : 'Future'}</span>
    `;
    list.appendChild(li);
  });
}

function formatCountdown(nextAtIso) {
  const target = new Date(nextAtIso).getTime();
  const diff = Math.max(0, target - Date.now());
  const hrs = Math.floor(diff / 3_600_000);
  const mins = Math.floor((diff % 3_600_000) / 60_000);
  const secs = Math.floor((diff % 60_000) / 1000);
  if (diff <= 0) return 'Ready now';
  return `Ready in ${hrs}h ${mins}m ${secs}s`;
}

function animateReels(finalSymbols) {
  const reels = [$('reel1'), $('reel2'), $('reel3')];
  const interimSymbols = ['🪙', '⚡', '🌀', '💎', '🦈', '🌊', '🎇', '✨'];
  reels.forEach((reel, idx) => {
    if (!reel) return;
    reel.classList.add('spinning');
    let tick = 0;
    const spinLoop = setInterval(() => {
      reel.textContent = interimSymbols[(tick + idx) % interimSymbols.length];
      tick += 1;
    }, 60);
    setTimeout(() => {
      clearInterval(spinLoop);
      reel.textContent = finalSymbols[idx];
      reel.classList.remove('spinning');
    }, 900 + idx * 140);
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
    await Promise.all([
      loadWheelRewards(),
      loadEvents(),
      loadAlbums(),
      loadDaily(),
      loadLeaderboard(),
      loadStore(),
      loadGlossary(),
      loadGuide(),
    ]);
  } else {
    $('result').textContent = resp.error || 'Authentication failed';
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
  $('result').textContent = 'Spinning...';
  const res = await postJSON('/api/spin', {
    token: state.token,
    multiplier: state.multiplier,
  });
  if (!res.ok) {
    $('result').textContent = res.error || 'Unable to spin right now.';
    return;
  }
  updateStats(res);
  if (res.result?.symbols) {
    animateReels(res.result.symbols);
  }
  const spinRewards = res.spin_rewards || res.result?.rewards || {};
  const rewardBits = [];
  if (spinRewards.coins) rewardBits.push(`🪙 +${spinRewards.coins}`);
  if (spinRewards.energy) rewardBits.push(`⚡ +${spinRewards.energy}`);
  if (spinRewards.wheel_tokens) rewardBits.push(`🌀 +${spinRewards.wheel_tokens}`);
  if (spinRewards.sticker_packs) rewardBits.push(`📔 +${spinRewards.sticker_packs}`);
  const rewardText = rewardBits.length ? rewardBits.join(' • ') : `🪙 +${res.payout}`;
  const label = res.result?.label ? ` (${res.result.label})` : '';
  $('result').textContent = `🎰 ${res.result?.label || 'Win'} → ${rewardText}${label}`;
  if (res.level_rewards && res.level_rewards.length) {
    const bonusText = res.level_rewards
      .map((reward) => `Lvl ${reward.level}: ${reward.description}`)
      .join(' • ');
    $('result').textContent += ` | 🎁 ${bonusText}`;
  }
  setTimeout(refreshState, 1200);
  await Promise.all([loadEvents(true), loadLeaderboard(true)]);
}

function renderWheel(rewards) {
  const wheel = $('fortuneWheel');
  if (!wheel) return;
  wheel.innerHTML = '';
  if (!rewards || !rewards.length) {
    wheel.textContent = 'No rewards configured yet';
    return;
  }
  wheel.style.transform = 'rotate(-15deg)';
  state.wheelRotation = -15;
  const slice = 360 / rewards.length;
  rewards.forEach((reward, index) => {
    const segment = document.createElement('div');
    segment.className = 'wheel-segment';
    segment.style.background = reward.color || '#02f2ff';
    segment.style.transform = `rotate(${index * slice}deg) skewY(${90 - slice}deg)`;
    const label = document.createElement('span');
    label.textContent = `${reward.label}`;
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
  const wheel = $('fortuneWheel');
  const message = $('wheelMessage');
  if (!wheel || !message) return;
  message.textContent = 'Wheel is spinning...';
  const res = await postJSON('/api/wheel/spin', { token: state.token });
  if (!res.ok) {
    message.textContent = res.error || 'No spins left.';
    return;
  }
  updateStats(res);
  const reward = res.reward;
  const meta = rewardMeta(reward.reward_type);
  message.textContent = `${meta.emoji} Wheel Reward: ${reward.label}`;
  animateWheelToReward(reward);
  await Promise.all([loadAlbums(true), loadEvents(true), loadLeaderboard(true)]);
}

function animateWheelToReward(reward) {
  const wheel = $('fortuneWheel');
  if (!wheel || !state.wheelRewards.length) return;
  const slice = 360 / state.wheelRewards.length;
  const index = state.wheelRewards.findIndex(
    (r) => r.label === reward.label && r.reward_type === reward.reward_type && r.amount === reward.amount,
  );
  const matchIndex = index >= 0 ? index : Math.floor(Math.random() * state.wheelRewards.length);
  const targetAngle = matchIndex * slice + slice / 2;
  const spins = 720;
  const finalRotation = state.wheelRotation + spins + (360 - targetAngle);
  wheel.style.transition = 'transform 3s cubic-bezier(0.25, 0.8, 0.25, 1)';
  wheel.style.transform = `rotate(${finalRotation}deg)`;
  setTimeout(() => {
    wheel.style.transition = '';
    state.wheelRotation = ((finalRotation % 360) + 360) % 360;
  }, 3100);
}

function renderEvents(events = []) {
  const container = $('eventsList');
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
    const rewardLabel = event.reward_type.replace(/_/g, ' ');
    const art = event.art_url ? `<img class="event-art" src="${event.art_url}" alt="${event.name}" />` : '';
    card.innerHTML = `
      <div class="event-top">
        <div class="event-icon">${event.emoji || '🎉'}</div>
        <div class="event-copy">
          <div class="status">${event.status.toUpperCase()}</div>
          <h3>${event.name}</h3>
          <p>${event.description}</p>
        </div>
      </div>
      ${art}
      <p class="event-reward">${event.emoji || '🎁'} Reward: ${event.reward_amount} ${rewardLabel}</p>
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

function renderAlbums(albums = [], duplicates = 0) {
  const container = $('albumsList');
  const duplicateLabel = $('duplicateCount');
  if (!container) return;
  container.innerHTML = '';
  if (duplicateLabel) {
    duplicateLabel.textContent = `${duplicates} duplicate stickers`;
  }
  if (!albums.length) {
    container.innerHTML = '<p>Sticker albums unlock soon!</p>';
    return;
  }
  albums.forEach((album) => {
    const card = document.createElement('article');
    card.className = 'album-card';
    if (album.theme?.accent) {
      card.style.setProperty('--album-accent', album.theme.accent);
    }
    if (album.theme?.background) {
      card.style.setProperty('--album-bg', `url(${album.theme.background})`);
    }
    const progressPct = Math.round((album.owned_count / album.total) * 100);
    const rewardTag = album.reward_claimed
      ? '✅ Reward claimed'
      : `${album.reward_spins} bonus spins`;
    const header = document.createElement('header');
    const img = document.createElement('img');
    const featured = album.stickers.find((s) => s.image_url);
    img.src = featured?.image_url || '/static/images/stickers/default.svg';
    img.alt = album.name;
    header.appendChild(img);
    const info = document.createElement('div');
    info.innerHTML = `<h3>${album.name}</h3><small>${album.description}</small>`;
    header.appendChild(info);
    const badge = document.createElement('span');
    badge.textContent = rewardTag;
    header.appendChild(badge);
    const stickerGrid = document.createElement('div');
    stickerGrid.className = 'album-stickers';
    stickerGrid.innerHTML = album.stickers
      .map(
        (sticker) => `
          <div class="sticker-tile">
            <div class="sticker-img"><img src="${sticker.image_url}" alt="${sticker.name}" /></div>
            <strong>${sticker.name}</strong>
            <span class="qty">${sticker.quantity ? `x${sticker.quantity}` : '—'}</span>
          </div>
        `,
      )
      .join('');
    const footer = document.createElement('footer');
    footer.innerHTML = `
      <div class="album-progress">${progressPct}% collected · ${album.owned_count}/${album.total}</div>
      <button class="secondary" data-album="${album.id}">Open Pack (${album.sticker_cost}🪙)</button>
    `;
    card.append(header, stickerGrid, footer);
    container.appendChild(card);
  });
}

function renderTradeSummary(trade) {
  const summary = $('tradeSummary');
  if (!summary) return;
  if (!trade || !trade.set_size) {
    summary.textContent = 'Collect more stickers to unlock trades.';
    return;
  }
  const sets = trade.sets_available || 0;
  const canTrade = sets > 0;
  summary.textContent = canTrade
    ? `You can trade ${sets} set${sets > 1 ? 's' : ''} of ${trade.set_size} duplicates for ${trade.coins}🪙 or ${trade.energy}⚡ per set.`
    : `Need ${trade.set_size} duplicate stickers to trade for ${trade.coins}🪙 or ${trade.energy}⚡.`;
}

async function loadAlbums(skipStats) {
  if (!state.token) return;
  const res = await getJSON(`/api/stickers?token=${encodeURIComponent(state.token)}`);
  if (res.ok) {
    if (!skipStats) updateStats(res);
    renderAlbums(res.albums || [], res.duplicates || 0);
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
    message += '\nAlbum completed! Spins and tokens added.';
  }
  alert(message);
  await loadAlbums(true);
}

async function tradeDuplicates(rewardType, sets = 1) {
  if (!state.token) return;
  const res = await postJSON('/api/stickers/trade', {
    token: state.token,
    reward_type: rewardType,
    sets,
  });
  if (!res.ok) {
    alert(res.error || 'Trade failed');
    return;
  }
  updateStats(res);
  alert(`Trade complete! ${Object.entries(res.reward)
    .map(([k, v]) => `${v} ${k}`)
    .join(' + ')}`);
  await loadAlbums(true);
}

async function loadDaily() {
  if (!state.token) return;
  const res = await getJSON(`/api/daily?token=${encodeURIComponent(state.token)}`);
  if (res.ok) {
    updateStats(res);
  }
}

async function claimDaily() {
  if (!state.token) return;
  const res = await postJSON('/api/daily/claim', { token: state.token });
  if (!res.ok) {
    alert(res.error || 'Daily reward not ready yet.');
    return;
  }
  updateStats(res);
  const reward = res.reward;
  const pieces = [`+${reward.coins}🪙`, `+${reward.energy}⚡`];
  if (reward.bonus_energy) pieces.push(`+${reward.bonus_energy}⚡ streak bonus`);
  if (reward.wheel_tokens) pieces.push(`+${reward.wheel_tokens}🌀`);
  if (reward.sticker_packs) pieces.push(`+${reward.sticker_packs}📔`);
  let msg = `Daily reward claimed! ${pieces.join(' ')}`;
  alert(msg);
}

function renderLeaderboard(leaderboard = {}) {
  const coinsList = $('leaderboardCoins');
  const xpList = $('leaderboardXp');
  if (!coinsList || !xpList) return;
  coinsList.innerHTML = '';
  xpList.innerHTML = '';
  const medals = ['🥇', '🥈', '🥉'];
  (leaderboard.coins || []).forEach((entry, index) => {
    const li = document.createElement('li');
    const rank = medals[index] || `#${index + 1}`;
    li.innerHTML = `<span>${rank} ${entry.username}</span><span>${entry.coins}🪙 · Lv ${entry.level}</span>`;
    coinsList.appendChild(li);
  });
  (leaderboard.xp || []).forEach((entry, index) => {
    const li = document.createElement('li');
    const rank = medals[index] || `#${index + 1}`;
    li.innerHTML = `<span>${rank} ${entry.username}</span><span>${entry.xp} XP · Lv ${entry.level}</span>`;
    xpList.appendChild(li);
  });
}

async function loadLeaderboard(skipStats) {
  if (!state.token) return;
  const res = await getJSON(`/api/leaderboard?token=${encodeURIComponent(state.token)}`);
  if (res.ok) {
    if (!skipStats) updateStats(res);
    renderLeaderboard(res.leaderboard || {});
  }
}

function renderStore(packages = []) {
  const container = $('starPackages');
  if (!container) return;
  container.innerHTML = '';
  if (!packages.length) {
    container.innerHTML = '<p>Star shop coming soon.</p>';
    return;
  }
  const tierIcons = ['🌊', '🧜‍♀️', '🐬', '🌈', '🐋', '🌌', '🚀', '🪐'];
  packages.forEach((pack, index) => {
    const card = document.createElement('div');
    card.className = 'shop-card';
    const art = pack.art_url ? `<img src="${pack.art_url}" alt="${pack.name}" />` : '';
    const tierBadge = `<span class="pack-tier">${tierIcons[index % tierIcons.length]} Tier ${index + 1}</span>`;
    const bonusSpins = pack.bonus_spins ?? 0;
    card.innerHTML = `
      ${tierBadge}
      ${art}
      <h3>${pack.name}</h3>
      <p class="pack-blurb">${pack.description || ''}</p>
      <p class="pack-stats">${pack.energy}⚡ energy + ${bonusSpins}🌀 wheel tokens</p>
      <strong>${pack.stars} ⭐</strong>
      <button class="primary" data-pack="${pack.id}">Purchase inside app</button>
    `;
    container.appendChild(card);
  });
}

async function loadStore() {
  if (!state.token) return;
  const res = await getJSON(`/api/store?token=${encodeURIComponent(state.token)}`);
  if (res.ok) {
    updateStats(res);
    renderStore(res.star_packages || []);
  }
}

function renderGlossary(glossary = []) {
  const container = $('glossaryList');
  if (!container) return;
  container.innerHTML = '';
  glossary.forEach((entry) => {
    const card = document.createElement('div');
    card.className = 'info-card';
    const art = entry.image_url ? `<img src="${entry.image_url}" alt="${entry.title}" />` : '';
    const details = Array.isArray(entry.details) && entry.details.length
      ? `<ul>${entry.details.map((d) => `<li>${d}</li>`).join('')}</ul>`
      : '';
    card.innerHTML = `
      ${art}
      <h3>${entry.emoji} ${entry.title}</h3>
      <p>${entry.body}</p>
      ${details}
    `;
    container.appendChild(card);
  });
}

async function loadGlossary() {
  if (!state.token) return;
  const res = await getJSON(`/api/glossary?token=${encodeURIComponent(state.token)}`);
  if (res.ok) {
    updateStats(res);
    renderGlossary(res.glossary || []);
  }
}

function renderGuide(guide = []) {
  const container = $('guideList');
  if (!container) return;
  container.innerHTML = '';
  if (!guide.length) {
    container.innerHTML = '<p class="guide-empty">Guides will appear here soon.</p>';
    return;
  }
  guide.forEach((entry) => {
    const card = document.createElement('article');
    card.className = 'guide-card';
    const steps = Array.isArray(entry.steps)
      ? entry.steps.map((step) => `<li>${step}</li>`).join('')
      : '';
    card.innerHTML = `
      <div class="guide-icon">${entry.emoji || '🧭'}</div>
      <div class="guide-copy">
        <h3>${entry.title || 'Guide'}</h3>
        <p>${entry.summary || ''}</p>
        ${steps ? `<ol>${steps}</ol>` : ''}
      </div>
    `;
    container.appendChild(card);
  });
}

async function loadGuide() {
  if (!state.token) return;
  const res = await getJSON(`/api/guide?token=${encodeURIComponent(state.token)}`);
  if (res.ok) {
    updateStats(res);
    renderGuide(res.guide || []);
  }
}

function setActiveNav(targetSelector, skipScroll = false) {
  if (!targetSelector) return;
  const section = document.querySelector(targetSelector);
  if (section && !skipScroll) {
    section.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
  document.querySelectorAll('[data-nav-target]').forEach((btn) => {
    btn.classList.toggle('active', btn.dataset.navTarget === targetSelector);
  });
  state.activeNav = targetSelector;
}

function registerSectionObserver() {
  const sections = document.querySelectorAll('[data-nav-section]');
  if (!('IntersectionObserver' in window) || !sections.length) return;
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          setActiveNav(`#${entry.target.id}`, true);
        }
      });
    },
    { threshold: 0.4 }
  );
  sections.forEach((section) => observer.observe(section));
}

function bindEvents() {
  $('spinBtn')?.addEventListener('click', spin);
  $('wheelSpinBtn')?.addEventListener('click', spinWheel);
  $('claimDailyBtn')?.addEventListener('click', claimDaily);
  document.querySelectorAll('.multiplier-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      state.multiplier = parseInt(btn.dataset.mult, 10);
      document.querySelectorAll('.multiplier-btn').forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
    });
  });
  $('albumsList')?.addEventListener('click', (ev) => {
    const target = ev.target.closest('button[data-album]');
    if (!target) return;
    const albumId = parseInt(target.dataset.album, 10);
    openSticker(albumId);
  });
  document.querySelector('.trade-buttons')?.addEventListener('click', (ev) => {
    const btn = ev.target.closest('button[data-trade]');
    if (!btn) return;
    const sets = parseInt(btn.dataset.sets || '1', 10);
    tradeDuplicates(btn.dataset.trade, Number.isNaN(sets) ? 1 : sets);
  });
  $('starPackages')?.addEventListener('click', (ev) => {
    const btn = ev.target.closest('button[data-pack]');
    if (!btn) return;
    buyStarPack(btn.dataset.pack);
  });
  document.querySelectorAll('[data-nav-target]').forEach((btn) => {
    btn.addEventListener('click', (ev) => {
      ev.preventDefault();
      const target = btn.dataset.navTarget;
      if (target) {
        setActiveNav(target);
      }
    });
  });
}

async function buyStarPack(packId) {
  if (!state.token) return;
  const res = await postJSON('/api/store/purchase', {
    token: state.token,
    pack_id: packId,
  });
  if (!res.ok) {
    alert(res.error || 'Unable to complete purchase right now.');
    return;
  }
  updateStats(res);
  const pack = res.pack || {};
  const energyGain = pack.energy ?? 0;
  const bonusSpins = pack.bonus_spins ? ` +${pack.bonus_spins}🌀` : '';
  alert(`⭐ ${pack.name || 'Star pack'} purchased! +${energyGain}⚡${bonusSpins}`);
}

window.addEventListener('DOMContentLoaded', () => {
  bindEvents();
  auth();
  if (tg) {
    tg.expand();
  }
  setActiveNav(state.activeNav, true);
  registerSectionObserver();

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
