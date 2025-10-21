# SharkSpin Admin Control Guide

Welcome aboard, captain. This document maps every switch you can flip inside the refreshed SharkSpin experience—from slot machine tuning to asset placement.

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

* Slot symbols, reward mixes, and multipliers are defined in `game_logic.py` via `SYMBOL_DEFINITIONS`.
* Spin energy cost = `Config.ENERGY_PER_SPIN`. Multipliers in the UI simply multiply that cost and the reward payload.
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
* Cooldown + token costs come from `Config.WHEEL_COOLDOWN_HOURS`, `Config.DAILY_FREE_WHEEL_SPINS`, and `Config.WHEEL_TOKEN_COST`.
* Wheel art layers sit in `static/images/wheel-glow.svg`, `wheel-frame.svg`, and `wheel-center.svg`. Replace those files with identically named assets to reskin the wheel.

## 5. Sticker Albums & Graphics

* Albums + stickers are defined by the `StickerAlbum` and `Sticker` tables.
  * Default seeding happens in `ensure_default_albums()` in `game_logic.py`.
  * Add or edit entries directly in the DB (use SQLite Browser or migrations) to grow the collection.
* Album completion rewards (extra spins + energy) are granted via `complete_album()`.
* Album card visuals pull iconography from `static/images/stickers/`—drop new SVG/PNG art there and reference it in `content.py` or custom templates if you extend the UI.

## 6. Live Events

* Events reside in the `live_events` table (`models.LiveEvent`).
* The helper `ensure_demo_event()` seeds a sample regatta; adjust this or insert new rows with start/end timestamps, spin targets, and reward payloads.
* Player progress is tracked in `event_progress`. Spins automatically advance the active event via `record_event_spin()` in `game_logic.py`.

## 7. Star Shop (In-App Purchases)

* Bundle catalog = `Config.STAR_PACKAGES`. Each dict supports: `id`, `name`, `stars`, `energy`, `bonus_spins`, `description`, and optional `art_url`.
* Assets referenced by `art_url` live in `static/images/` (e.g., `star-pack-coral.svg`). Replace or add SVGs there for new bundle art.
* The web app calls `/api/shop` for catalog data and `/api/shop/order` to create Telegram Stars invoices through `createInvoiceLink`.
* Ensure `TELEGRAM_BOT_TOKEN` and `BOT_USERNAME` are configured so `_build_invoice_link` in `app.py` can reach Telegram.
* Payments are still acknowledged through `successful_payment` in `bot.py`. Keep the bot running to grant energy/tokens after Stars payments complete.

## 8. Web App Content & Navigation

* `templates/index.html` – markup for the new command deck (hero, slot machine, wheel, shop, help, etc.).
* `static/styles.css` – casino styling, slot machine chrome, wheel lighting, and responsive layouts.
* `static/game.js` – client logic for authentication, slot spins, wheel spins, daily rewards, shop invoicing, navigation, and guide rendering.
* `content.py` – editable narrative data for the “Operations Briefing” callouts, guide sections, and taskbar structure. Update this file to change copy or add new help sections without touching JS.
* Additional assets:
  * `static/images/slot-*.svg` for the slot machine bezel and lights.
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
