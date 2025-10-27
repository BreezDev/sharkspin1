# SharkSpin Admin Control Guide

Welcome aboard, captain. This document maps every switch you can flip inside the refreshed SharkSpin experience—from slot machine tuning to asset placement.

## 0. Quick Admin Control Map

| Feature | Where to edit | Notes |
| --- | --- | --- |
| Slot symbols, payouts, "no reward" odds | `/admin/slot-symbols` in **adminpanel.py** | Adjust emoji, descriptions, reward payloads, and `weight` to influence hit rates. Toggle `is_enabled` to temporarily remove a symbol. |
| Coin cost, energy cost, multiplier presets | `config.py` (`COIN_COST_PER_SPIN`, `ENERGY_PER_SPIN`, `SPIN_MULTIPLIER_PRESETS`) | The web app reads these values and exposes them in the wager HUD. |
| Albums & sticker packs | `/admin/albums` + `/admin/stickers` APIs | Seed defaults via `ensure_default_albums` or curate directly from the admin panel. |
| Live + seasonal events & rewards | `/admin/events` | Create, edit, or retire entries. The helper `ensure_signature_events` (game_logic.py) seeds the three showcase events and banner art. |
| Wheel of Tides slices & odds | `/admin/wheel` | Edit label, reward type/amount, slice color, and `weight` (higher = more common) to reshape the wheel. |
| Star Shop catalog | `/admin/shop` | Add/remove in-app purchases, toggle availability, or retheme art and descriptions without redeploying. Bonus spin inputs clamp to either 0 or +1 Wheel Token. |
| Reward links & broadcast messages | `/admin/rewards`, `/admin/broadcasts` | Generate redeemable links, inspect redemptions, or send Telegram broadcasts with reward URLs. |
| Leaderboard weekly payouts | `/admin/leaderboard` | Issue SharkCoin/energy rewards to the top captains from the dashboard. |

## 1. Platform Configuration

| Setting | Purpose | Default | Where to edit |
| --- | --- | --- | --- |
| `SECRET_KEY` | Flask + signer secret | `dev-secret-key` | environment or `.env` |
| `DATABASE_URL` | SQLAlchemy connection URI | sqlite path | environment |
| `WEBAPP_URL` | Public HTTPS URL of the Flask app (used by bot/web app links) | sample PA URL | `config.py` / env |
| `TELEGRAM_BOT_TOKEN` | Telegram bot API token (needed for invoices + updates) | — | env |
| `BOT_USERNAME` | Telegram bot username without `@` (used for invoice fallbacks) | `SharkSpinBot` | env |
| `ADMIN_SECRET` | REST admin auth | `super-shark-admin` | env |
| `STARTING_COINS` / `STARTING_ENERGY` | Initial wallet values | `100` / `30` | `config.py` |
| `DAILY_*` settings | Daily reward scaling and milestones | see file | `config.py` |
| `LEVEL_XP_CURVE`, `LEVEL_REWARDS` | Level thresholds + auto payouts | list/dict | `config.py` |
| `STAR_PACKAGES` | Star shop bundles (id, stars, energy, bonus spins, art) | seven presets | `config.py` |

> ⚠️ Always restart both the Flask app and the bot after altering environment variables.

## 2. Slot Machine & Economy

* Spin wagers now consume **energy and SharkCoins**. Configure the base drain through:
  * `Config.ENERGY_PER_SPIN` – energy drained per multiplier tier (default 3⚡).
  * `Config.COIN_COST_PER_SPIN` – coins removed per multiplier tier (default 75🪙).
  * `Config.SPIN_MULTIPLIER_PRESETS` – the selectable multipliers surfaced in the wager HUD.
* Slot symbols, reward mixes, and "no loot" odds are editable through the admin panel (`/admin/slot-symbols`) or directly inside `game_logic.ensure_default_slot_symbols()`.
* House edge tuning now lives in `Config.SPIN_PAYOUT_COINS_SCALAR`, `SPIN_PAYOUT_ENERGY_SCALAR`, `SPIN_PAYOUT_TOKEN_SCALAR`, and `SPIN_BRICK_CHANCE`. Lower the scalars or raise the brick chance to make the machine harsher.
* Level progress uses `user.total_earned` against the thresholds returned by `_xp_threshold` (see `app.py`). Update `Config.LEVEL_XP_CURVE` and `LEVEL_REWARDS` to re-balance XP pacing or bonus drops.

## 3. Daily Rewards

* State is stored in the new `daily_reward_state` table (`models.DailyRewardState`).
* Claim cadence = 24 hours (`/api/daily/claim`). Missing 48 hours resets the streak.
* Tweak rewards in `config.py`:
  * `DAILY_REWARD_BASE_COINS`
  * `DAILY_REWARD_BASE_ENERGY`
  * `DAILY_STREAK_BONUS`
  * `DAILY_MILESTONES` (array of streak days that add +1 Wheel Token)
* The web app preview card consumes `/api/daily`, which now returns `next_reward`, `seconds_until`, and `milestones`.

## 4. Wheel of Tides

* Rewards live in the `wheel_rewards` table. Update via SQL or adjust defaults in `ensure_default_wheel_rewards` inside `game_logic.py`.
* The admin dashboard exposes a **Wheel Rewards** form (`/admin/wheel`). Edit label, reward type, amount, color, and `weight` (probability weight) to rebalance slices on the fly.
* Wheel token slice amounts are auto-capped to a single token—entering larger numbers will still publish as 1.
* Cooldown + token costs come from `Config.WHEEL_COOLDOWN_HOURS`, `Config.DAILY_FREE_WHEEL_SPINS`, and `Config.WHEEL_TOKEN_COST`.
* Wheel art layers sit in `static/images/wheel-glow.svg`, `wheel-frame.svg`, and `wheel-center.svg`. Replace those files with identically named assets to reskin the wheel.

## 5. Sticker Albums & Graphics

* Albums + stickers are defined by the `StickerAlbum` and `Sticker` tables.
  * Default seeding happens in `ensure_default_albums()` in `game_logic.py`.
  * Add or edit entries directly in the DB (use SQLite Browser or migrations) to grow the collection.
* Album completion rewards (extra spins + energy) are granted via `complete_album()`.
* Album card visuals pull iconography from `static/images/stickers/`—drop new SVG/PNG art there and reference it in `content.py` or custom templates if you extend the UI.

## 6. Live Events

* Events reside in the `live_events` table (`models.LiveEvent`). Maintain them in bulk from `/admin/events`.
* The helper `ensure_signature_events()` (game_logic.py) seeds three showcase campaigns (Grand Regatta, Abyssal Bounty Hunt, Turbine Frenzy). Update the definitions there to change banners, timing, or default rewards.
* Event art lives under `static/images/events/`. Swap in new SVGs and adjust each event's `banner_url`.
* Player progress is tracked in `event_progress`. Every spin updates all live events via `record_event_spin()` and automatically awards their configured rewards when goals are met.

## 7. Star Shop (In-App Purchases)

* Bundle catalog = `Config.STAR_PACKAGES`. Each dict supports: `id`, `name`, `stars`, `energy`, `bonus_spins`, `description`, and optional `art_url`.
* Live bundles can also be created or retired from the **Star Shop** card in `/admin/shop`. Toggle `is_active` to soft-delete offers without code changes.
* Assets referenced by `art_url` live in `static/images/` (e.g., `star-pack-coral.svg`). Replace or add SVGs there for new bundle art.
* The web app calls `/api/shop` for catalog data and `/api/shop/order` to create Telegram Stars invoices through `createInvoiceLink`.
* Bonus spin fields in the admin panel and API are sanitized to 0 or +1 so wheel tokens stay rare.
* Ensure `TELEGRAM_BOT_TOKEN` and `BOT_USERNAME` are configured so `_build_invoice_link` in `app.py` can reach Telegram.
* Payments are still acknowledged through `successful_payment` in `bot.py`. Keep the bot running to grant energy/tokens after Stars payments complete.

## 8. Web App Content & Navigation

* `templates/index.html` – markup for the neon slot landing page, leaderboard lounge, wheel, albums, and shop views.
* `static/styles.css` – casino styling, slot machine chrome, wheel lighting, marquee ticker, and responsive layouts.
* `static/game.js` – client logic for authentication, slot spins, wheel spins, daily rewards, shop invoicing, navigation, and guide rendering. The wager HUD pulls values from the API (coin cost, energy cost, multipliers).
* `content.py` – editable narrative data for the “Operations Briefing” callouts and the taskbar structure. The new taskbar order lives in `TASKBAR_LINKS`; set the `default` flag on whichever view should load first.
* Additional assets:
  * `static/images/slot-*.svg` for the slot machine bezel and lights.
  * `static/images/events/*.svg` for event spotlights.
  * `static/images/daily-chest.svg` for the daily reward hero.
  * `static/images/info-*.svg` for informational callouts.

## 9. Telegram Bot Operations

* Supported public commands: `/start`, `/me`, `/buy` (plus admin-only `/reward`).
* `/start` now replies with a single mini-app launch button (no inline shop lists).
* `/buy` summarizes available Star packs and directs users back to the in-app shop tab.
* `/reward` (admin only) issues a startapp link that launches the mini app automatically using an inline WebApp button.
* All conversation and purchasing flows are anchored inside the mini app; the bot only acts as a launcher or receipt channel.

## 10. Image & Asset Management

| Location | Purpose |
| --- | --- |
| `static/images/` | Wheel art, slot components, star pack badges, info icons |
| `static/images/stickers/` | Sticker-specific graphics (extend as you add albums) |
| `static/images/event-*.svg` | Event hero art (swap for seasonal campaigns) |
| `templates/index.html` | Reference paths when adding new imagery to the UI |

To add new imagery, drop the asset into the appropriate folder and update the referencing `art_url` (for shop packs) or markup in `index.html` / `content.py`.

## 11. Database Tables

| Table | Notes |
| --- | --- |
| `users` | Core profile (coins, energy, level, wheel tokens, total earned) |
| `daily_reward_state` | Tracks streak, total claims, last claim timestamp |
| `wheel_rewards` | Wheel of Tides slices (label, color, amount, weight) |
| `sticker_albums` / `stickers` | Album metadata and sticker inventory |
| `event_progress` / `live_events` | Live event definitions & user progress |
| `reward_links` | Signed reward tokens for campaigns |
| `payments` | Telegram Stars purchase receipts |

## 12. Deployment Checklist

1. **Secrets** – populate all env vars listed in section 1.
2. **Database** – run `Base.metadata.create_all(engine)` once (the app already does this on boot) or apply migrations for existing installs.
3. **Assets** – upload new art to `static/images/` if you are branding the release.
4. **Bot** – start `python bot.py` (polling) or configure a webhook; ensure the bot has access to the same database as the web app.
5. **Invoice Test** – call `/api/shop/order` from the web app and verify `tg.openInvoice` launches a Stars payment sheet. Confirm the bot logs a `successful_payment` update and grants energy/tokens.
6. **Reward Link Test** – run `/reward coins 100 1`, tap the inline button from Telegram, and verify the mini app auto-claims the reward.

Stay vigilant and keep the tides thrilling! 🦈
