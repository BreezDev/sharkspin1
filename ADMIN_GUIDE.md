# SharkSpin Admin Control Guide

Welcome aboard, reef master! This guide outlines every lever available to operators of the SharkSpin experience.

## 1. Environment Setup

| Setting | Purpose | Default |
| --- | --- | --- |
| `SECRET_KEY` | Flask + signing secrets | `dev-secret-key` |
| `DATABASE_URL` | SQLAlchemy connection string | `sqlite:////home/tofumochi/sharkspin/sharkspin.db` |
| `TELEGRAM_BOT_TOKEN` | Bot token for Stars + chat commands | — |
| `ADMIN_SECRET` | Shared secret for admin REST endpoints | `super-shark-admin` |
| `WEBAPP_URL` | Hosted mini-app base URL | `https://game-tofumochi.pythonanywhere.com` |
| `STARTING_COINS` | New player wallet | `100` |
| `STARTING_ENERGY` | New player energy | `30` |
| `DAILY_REWARD_BASE_COINS` | Base daily coins | `200` |
| `DAILY_REWARD_BASE_ENERGY` | Base daily energy | `6` |
| `LEVEL_XP_CURVE` | XP thresholds for levels | See `config.py` |
| `LEVEL_REWARDS` | Level milestone payouts | See `config.py` |
| `STAR_PACKAGES` | Star Market bundle catalog | 7 neon bundles |

> 🔐 Update secrets via environment variables before deploying to production.

## 2. Reward Links

Two entry points exist for generating mini-app reward links:

### 2.1 Telegram `/reward` Bot Command

```
/reward <coins|energy|spins|wheel_tokens|sticker_pack> <amount> <uses>
```

* Only usable by the Telegram user ID defined in `ADMIN_ID` inside `bot.py`.
* Automatically stores (or refreshes) the reward in the `reward_links` table and replies with a signed `startapp` URL, e.g. `https://t.me/<bot_username>/startapp?startapp=redeem_<token>`.
* Re-using the same type/amount regenerates the link, resets `uses_left` to the new value, and re-activates the token.
* Delivered rewards credit coins, energy, wheel tokens, or sticker pack tokens inside the mini app.

### 2.2 REST Endpoint `/api/admin/reward-link`

```http
POST /api/admin/reward-link
Content-Type: application/json
{
  "admin_secret": "super-shark-admin",
  "reward_type": "coins",
  "amount": 500,
  "uses": 10,
  "created_by": "ops-dashboard",
  "bot_username": "SharkSpinBot"
}
```

* Requires `admin_secret` to match `Config.ADMIN_SECRET`.
* Returns `{ token, reward_url, uses, summary }` so you can blast rewards via Telegram messages or campaigns.
* Re-using the same `token` re-activates the link, updates the reward payload, and sets `uses_left` to the requested number.

### 2.3 Verification Checklist

Run these quick checks anytime rewards feel off:

1. `/reward coins 100 5` should reply with a MarkdownV2 card containing a startapp link. Tap it inside Telegram to ensure the mini app opens to the redeem screen.
2. Inspect the `reward_links` table — the `token` from step 1 should be present with `uses_left = 5` and `is_active = 1`.
3. Call `POST /api/admin/reward-link` with a different payload and confirm the JSON response includes `reward_url`.
4. Visit the generated URL using `?tg_user_id=<your_id>` and watch the `uses_left` decrement after the first claim.
5. Attempt an extra claim after uses drop to `0`; the redeem page must display the "expired" warning.

> 💡 Tip: `bot.py` escapes Markdown automatically. If the Telegram message shows raw characters, update to the latest bot script in this repo.

## 3. Daily Rewards & Streaks

* Players can claim once every 20 hours (`/api/daily/claim`).
* Streaks reset if a player misses 36 hours.
* Every 7-day streak grants +1 wheel token, +1 sticker pack token, and an energy burst (see `Config.DAILY_STREAK_BONUS`).
* `/api/daily` now returns `reward`, `next_reward`, and `milestones` so dashboards can preview upcoming streak loot exactly as the mini app does.

## 4. Level Progression

* XP accrues with every slot spin (see `calc_spin_xp`).
* Thresholds & rewards live in `Config.LEVEL_XP_CURVE` and `Config.LEVEL_REWARDS`.
* Reward types include coins, energy, wheel tokens, free sticker packs, spins (energy), and legendary stickers.
* Level rewards are auto-granted during `/api/spin` when milestones are crossed and logged to the response payload.

## 5. Wheel of Tides

* Default catalog is seeded by `ensure_default_wheel_rewards()`.
* Wheel cooldown is `Config.WHEEL_COOLDOWN_HOURS`. Players can burn `wheel_tokens` if the free spin isn’t ready.
* Jackpot configuration (label, weight, color) is stored in the `wheel_rewards` table—edit rows via SQL or create admin tooling as needed.

## 6. Sticker Albums & Trading

* Albums and sticker metadata are stored in the `sticker_albums` and `stickers` tables.
* Completing an album grants extra wheel tokens and energy (see `complete_album`).
* Duplicates can be traded via `/api/stickers/trade` in batches of `Config.STICKER_TRADE_SET_SIZE`. Each set pays `Config.STICKER_TRADE_COINS` coins or `Config.STICKER_TRADE_ENERGY` energy (the mini app surfaces both options and available set counts).
* Level rewards and wheel spins can drop **sticker pack tokens** that bypass coin costs when opening packs.
* To add an album: create a row in `sticker_albums` (name, slug, reward_spins, sticker_cost) then insert related sticker rows. Update `image_url` with SVG paths from `static/images/stickers/`.
* Default seeding lives in `game_logic.ensure_default_albums()`—extend this helper for code-based deployments or seed via SQL for production.
* Swap sticker artwork by replacing the SVG in `static/images/stickers/` and updating `Sticker.image_url` to point at the new file.

## 7. Live Events

* Demo event seeded by `ensure_demo_event()`—update the row to schedule timed events.
* Progress is incremented during `/api/spin`; rewards can be coins, spins (energy), or wheel tokens.
* Extend by inserting additional `live_events` records with your desired windows and thresholds.
* Art assets for events live under `static/images/event-*.svg`; update references via the `image_url` column if you add themed graphics.

## 8. In-App Star Market

* Configure bundled packs with `Config.STAR_PACKAGES` (id, stars, energy, bonus spins, description, art).
* The mini app calls `POST /api/store/purchase` to grant energy + wheel tokens instantly and record the sale in `payments` (look for `tg_payment_charge_id` prefixed with `WEBAPP-`).
* Telegram bot `/buy` now simply opens the web app Star Market—no invoices are sent from chat.
* Update pack art by replacing the SVGs in `static/images/star-pack-*.svg`; reference names inside each package definition.
* Add or remove bundles by editing the `STAR_PACKAGES` list. Fields are read directly by both backend responses and the web app UI.

## 9. Mini App Content & Help

* Navigation taskbar buttons live at the bottom of `templates/index.html`. Update labels or targets by editing the `<nav class="taskbar">` block.
* Sections that sync with the taskbar carry the `data-nav-section` attribute—add it to new panels so the IntersectionObserver in `static/game.js` can highlight the active tab.
* The in-app Help Center pulls from `/api/guide` defined in `app.py`. Edit the guide list there or adjust copy in `USER_GUIDE.md` (mirrors the same information for documentation).
* Glossary tiles are served from `/api/glossary`; update descriptions or imagery references inside the same function.
* Wheel artwork overlays are SVGs inside `static/images/wheel-*.svg` (`wheel-frame`, `wheel-glow`, `wheel-center`). Swap these files to refresh styling.
* Hero, shop, and sticker art assets sit under `static/images/` (see folders for albums, stickers, and events). Replace SVGs and update DB paths as needed.

## 10. Deployment Checklist

1. **Set Secrets**: `SECRET_KEY`, `TELEGRAM_BOT_TOKEN`, `ADMIN_SECRET`.
2. **Migrate Database**: The app auto-creates tables (`Base.metadata.create_all`). For existing installs, run migrations when schema changes.
3. **Seed Data**: `ensure_default_wheel_rewards`, `ensure_default_albums`, and `ensure_demo_event` run on every request via `@app.before_request`.
4. **Bot**: Deploy `bot.py` with `python bot.py` or integrate into your infrastructure. Set webhooks if required.
5. **Mini App**: Host Flask app, configure Telegram WebApp URL, and provide support links for users.

## 11. Troubleshooting

| Symptom | Resolution |
| --- | --- |
| Daily reward button stuck | Verify system clock and ensure `last_daily_claim_at` resets after 36h. |
| Wheel spins unavailable | Confirm player has tokens or cooldown expired; adjust `WHEEL_COOLDOWN_HOURS`. |
| Reward links rejected | Check `ADMIN_SECRET`, ensure link token stored in DB, and confirm uses_left > 0. |
| Star purchase not crediting | Check `/api/store/purchase` logs, confirm `WEBAPP-` payments in the database, and verify the pack ID exists in `STAR_PACKAGES`. |

## 11. Support Scripts

*Generate reward link from shell:*
```python
from itsdangerous import URLSafeSerializer
from config import Config
signer = URLSafeSerializer(Config.SECRET_KEY, salt="sharkspin:reward")
print(signer.dumps({"type": "coins", "amount": 250}))
```

*Reset a user streak:*
```sql
UPDATE users SET daily_streak = 0, last_daily_claim_at = NULL WHERE tg_user_id = '<id>';
```

Dive safe and keep the tides thrilling! 🦈
