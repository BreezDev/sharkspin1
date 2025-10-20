const tg = window.Telegram?.WebApp;
let TOKEN = null;
let multiplier = 1;

async function postJSON(url, data){
  const res = await fetch(url, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)});
  return await res.json();
}

async function getJSON(url){
  const res = await fetch(url);
  return await res.json();
}

// AUTH
async function auth(){
  const user = tg?.initDataUnsafe?.user;
  const tg_user_id = user?.id?.toString() || prompt('Enter Test TG ID');
  const username = user?.username || 'webapp_user';
  const resp = await postJSON('/api/auth', { tg_user_id, username });
  if(resp.ok){
    TOKEN = resp.token;
    document.getElementById('coins').textContent = resp.coins;
    document.getElementById('energy').textContent = resp.energy;
  }
}

// REFRESH
async function refreshMe(){
  const u = await getJSON('/api/me?token='+encodeURIComponent(TOKEN));
  if(u.ok){
    document.getElementById('coins').textContent = u.coins;
    document.getElementById('energy').textContent = u.energy;
  }
}

// SPIN
async function spin(){
  const res = await postJSON('/api/spin', { token:TOKEN, multiplier });
  if(!res.ok){
    document.getElementById('result').textContent = res.error || 'Error';
    return;
  }

  // Visual slot results
  const reels = res.result;
  document.getElementById('reel1')?.textContent = reels[0];
  document.getElementById('reel2')?.textContent = reels[1];
  document.getElementById('reel3')?.textContent = reels[2];

  document.getElementById('coins').textContent = res.coins;
  document.getElementById('energy').textContent = res.energy;
  document.getElementById('level')?.textContent = res.level;

  document.getElementById('result').textContent = `+${res.payout} SharkCoins 🦈`;
}

// BUY ENERGY (Stars)
async function buyEnergy(){
  const botUsername = tg?.initDataUnsafe?.receiver?.username || 'YOUR_BOT_USERNAME';
  const url = `https://t.me/${botUsername}?start=buy`;
  if(tg?.openTelegramLink){
    tg.openTelegramLink(url);
  } else {
    window.open(url, '_blank');
  }
}

// MULTIPLIERS
document.querySelectorAll('.multiplier-btn')?.forEach(btn=>{
  btn.addEventListener('click', ()=>{
    multiplier = parseInt(btn.dataset.mult);
    document.querySelectorAll('.multiplier-btn').forEach(b=>b.classList.remove('active'));
    btn.classList.add('active');
  });
});

// INIT
window.addEventListener('DOMContentLoaded', () =>{
  document.getElementById('spinBtn')?.addEventListener('click', spin);
  document.getElementById('buyEnergyBtn')?.addEventListener('click', buyEnergy);
  auth();
  if(tg){ tg.expand(); }

  // Check for Telegram deep link param (reward)
  const userId = tg?.initDataUnsafe?.user?.id;
  const startParam = tg?.initDataUnsafe?.start_param; // e.g. redeem_<token>
  if(startParam && startParam.startsWith("redeem_")){
    const token = startParam.replace("redeem_", "");
    if(!userId){
      alert("You must open this link inside Telegram to claim rewards.");
    } else {
      fetch(`/redeem/${token}?tg_user_id=${userId}`)
        .then(r=>r.text())
        .then(html=>{
          // Replace body temporarily to show redeem message
          document.body.innerHTML = html;
        });
    }
  }
});
