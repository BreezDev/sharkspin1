from datetime import datetime, timedelta
from typing import Any, Dict

from flask import Flask, abort, jsonify, render_template, request
from sqlalchemy import select
from sqlalchemy.orm import joinedload, sessionmaker
from itsdangerous import URLSafeSerializer, BadSignature

from config import Config
from models import (
    AlbumCompletion,
    Base,
    EventProgress,
    LiveEvent,
    Payment,
    RewardLink,
    Spin,
    StickerAlbum,
    User,
    UserSticker,
    WheelReward,
    WheelSpin,
)
from game_logic import (
    apply_spin,
    calculate_level_progress,
    complete_album,
    ensure_default_albums,
    ensure_default_wheel_rewards,
    ensure_demo_event,
    grant_sticker,
    pull_sticker,
    record_event_spin,
    resolve_level_rewards,
    serialize_event,
    spin_wheel,
    trade_stickers_for_reward,
)

from sqlalchemy import create_engine

app = Flask(__name__)
app.config.from_object(Config)

engine = create_engine(Config.SQLALCHEMY_DATABASE_URI, future=True)
Session = sessionmaker(bind=engine, expire_on_commit=False, future=True)
Base.metadata.create_all(engine)

# Sign mini app init data (optional – extra layer beyond Telegram WebApp initData)
signer = URLSafeSerializer(Config.SECRET_KEY, salt="sharkspin:webapp")
reward_signer = URLSafeSerializer(Config.SECRET_KEY, salt="sharkspin:reward")


@app.before_request
def bootstrap_catalogs():
    # Ensure default data exists before handling requests that need them
    with Session() as s:
        ensure_default_wheel_rewards(s)
        ensure_default_albums(s)
        ensure_demo_event(s)


@app.get("/")
def index():
    return render_template("index.html")


def generate_reward_link(amount: int = 100, type_: str = "coins") -> str:
    payload = {"type": type_, "amount": amount}
    token = reward_signer.dumps(payload)
    base_url = Config.WEBAPP_URL.rstrip("/")
    return f"{base_url}/redeem/{token}"


@app.get("/redeem/<token>")
def redeem_reward(token):
    try:
        reward = reward_signer.loads(token)
    except Exception:
        return render_template("redeem.html", message="❌ Invalid or expired reward link.")

    tg_user_id = request.args.get("tg_user_id")
    if not tg_user_id or tg_user_id == "{tg_user_id}":
        return render_template(
            "redeem.html",
            message="⚠️ You must open this link inside SharkSpin (Telegram Mini App).",
        )

    with Session() as s:
        rl = s.execute(select(RewardLink).where(RewardLink.token == token)).scalar_one_or_none()
        if not rl or not rl.is_active or rl.uses_left <= 0:
            return render_template(
                "redeem.html", message="🚫 This reward link has expired or was already used."
            )

        user = s.execute(select(User).where(User.tg_user_id == str(tg_user_id))).scalar_one_or_none()
        if not user:
            return render_template(
                "redeem.html",
                message="❌ You don’t have a SharkSpin account yet! Use /start first.",
            )

        if rl.reward_type == "coins":
            user.coins += rl.amount
        elif rl.reward_type == "energy":
            user.energy += rl.amount
        elif rl.reward_type == "spins":
            user.energy += rl.amount * Config.ENERGY_PER_SPIN
        elif rl.reward_type == "wheel_tokens":
            user.wheel_tokens += rl.amount
        elif rl.reward_type == "sticker_pack":
            user.free_sticker_packs += rl.amount
        else:
            return render_template("redeem.html", message="❌ Invalid reward type.")

        rl.uses_left -= 1
        if rl.uses_left <= 0:
            rl.is_active = False

        s.commit()

        reward_text_map = {
            "coins": f"{rl.amount} SharkCoins 🪙",
            "energy": f"{rl.amount} Energy ⚡",
            "spins": f"{rl.amount} Free Spins 🎰",
            "wheel_tokens": f"{rl.amount} Wheel Tokens 🌀",
            "sticker_pack": f"{rl.amount} Sticker Pack Tokens 📔",
        }
        reward_text = reward_text_map.get(rl.reward_type, f"{rl.amount} {rl.reward_type}")
        remaining = max(rl.uses_left, 0)
        msg = f"🎁 You received {reward_text}! ({remaining} uses left)"
        return render_template("redeem.html", message=msg)


@app.post("/api/auth")
def api_auth():
    data = request.get_json(force=True)
    tg_user_id = str(data.get("tg_user_id"))
    username = data.get("username")
    if not tg_user_id:
        abort(400)

    with Session() as s:
        user = s.execute(select(User).where(User.tg_user_id == tg_user_id)).scalar_one_or_none()
        if not user:
            user = User(
                tg_user_id=tg_user_id,
                username=username,
                coins=Config.STARTING_COINS,
                energy=Config.STARTING_ENERGY,
                wheel_tokens=Config.DAILY_FREE_WHEEL_SPINS,
            )
            s.add(user)
            s.commit()
        token = signer.dumps({"u": tg_user_id})
        payload = serialize_user_state(user)
        payload.update({"ok": True, "token": token})
        return jsonify(payload)


def _level_summary(user: User) -> Dict[str, Any]:
    info = calculate_level_progress(user.xp)
    reward_preview = Config.LEVEL_REWARDS.get(info["next_level"])
    return {
        **info,
        "reward_preview": reward_preview,
        "claimed_upto": user.level_reward_checkpoint,
    }


def _daily_reward_for_day(day: int) -> Dict[str, Any]:
    coins = Config.DAILY_REWARD_BASE_COINS + max(day - 1, 0) * 15
    energy = Config.DAILY_REWARD_BASE_ENERGY
    bonus_energy = Config.DAILY_STREAK_BONUS if day % 7 == 0 else 0
    wheel_tokens = 1 if day % 7 == 0 else 0
    sticker_packs = 1 if day % 7 == 0 else 0
    return {
        "day": day,
        "coins": coins,
        "energy": energy,
        "bonus_energy": bonus_energy,
        "wheel_tokens": wheel_tokens,
        "sticker_packs": sticker_packs,
    }


def _daily_summary(user: User) -> Dict[str, Any]:
    now = datetime.utcnow()
    next_reset = None
    can_claim = True
    if user.last_daily_claim_at:
        elapsed = now - user.last_daily_claim_at
        if elapsed < timedelta(hours=20):
            can_claim = False
            next_reset = (user.last_daily_claim_at + timedelta(hours=20)).isoformat()
    next_day = user.daily_streak + 1
    reward = _daily_reward_for_day(next_day)
    next_reward = _daily_reward_for_day(next_day + 1)
    milestones = []
    for day in Config.DAILY_MILESTONES:
        info = _daily_reward_for_day(day)
        info["achieved"] = user.daily_streak >= day
        info["upcoming"] = next_day == day
        milestones.append(info)
    return {
        "streak": user.daily_streak,
        "can_claim": can_claim,
        "next_available_at": next_reset,
        "reward": reward,
        "next_reward": next_reward,
        "milestones": milestones,
    }


def serialize_user_state(user: User) -> Dict[str, Any]:
    return {
        "coins": user.coins,
        "energy": user.energy,
        "level": user.level,
        "xp": user.xp,
        "lifetime_spins": user.lifetime_spins,
        "wheel_tokens": user.wheel_tokens,
        "free_sticker_packs": user.free_sticker_packs,
        "last_wheel_spin_at": user.last_wheel_spin_at.isoformat()
        if user.last_wheel_spin_at
        else None,
        "daily": _daily_summary(user),
        "level_summary": _level_summary(user),
    }


def _get_user_from_token(token):
    try:
        payload = signer.loads(token)
        tg_user_id = payload.get("u")
    except BadSignature:
        return None
    with Session() as s:
        return s.execute(select(User).where(User.tg_user_id == str(tg_user_id))).scalar_one_or_none()


@app.post("/api/spin")
def api_spin():
    payload = request.get_json(force=True)
    token = payload.get("token")
    multiplier = int(payload.get("multiplier", 1))
    user = _get_user_from_token(token)
    if not user:
        abort(401)
    with Session() as s:
        user = s.merge(user)
        previous_level = user.level
        ok, msg, payout, result_data = apply_spin(user, multiplier=multiplier)
        if not ok:
            return jsonify({"ok": False, "error": msg}), 200
        spin_rewards = result_data.get("rewards", {})
        rec = Spin(
            user_id=user.id,
            delta_coins=spin_rewards.get("coins", payout),
            result=result_data["label"],
        )
        s.add(rec)
        record_event_spin(s, user, multiplier)
        level_rewards = resolve_level_rewards(s, user, previous_level)
        s.commit()
        response = {
            "ok": True,
            "payout": payout,
            "result": result_data,
            "level_rewards": level_rewards,
            "spin_rewards": spin_rewards,
        }
        response.update(serialize_user_state(user))
        return jsonify(response)


@app.get("/api/me")
def api_me():
    token = request.args.get("token")
    user = _get_user_from_token(token)
    if not user:
        abort(401)
    return jsonify({"ok": True, **serialize_user_state(user)})


@app.get("/api/wheel")
def api_wheel_catalog():
    token = request.args.get("token")
    user = _get_user_from_token(token)
    if not user:
        abort(401)
    with Session() as s:
        rewards = s.query(WheelReward).all()
        data = [
            {
                "id": r.id,
                "label": r.label,
                "reward_type": r.reward_type,
                "amount": r.amount,
                "color": r.color,
                "weight": r.weight,
            }
            for r in rewards
        ]
        return jsonify({"ok": True, "rewards": data, **serialize_user_state(user)})


@app.post("/api/wheel/spin")
def api_wheel_spin():
    payload = request.get_json(force=True)
    token = payload.get("token")
    user = _get_user_from_token(token)
    if not user:
        abort(401)

    with Session() as s:
        user = s.merge(user)
        rewards = ensure_default_wheel_rewards(s)

        now = datetime.utcnow()
        free_available = False
        if user.last_wheel_spin_at is None:
            free_available = True
        else:
            diff = now - user.last_wheel_spin_at
            free_available = diff >= timedelta(hours=Config.WHEEL_COOLDOWN_HOURS)

        if not free_available:
            if user.wheel_tokens < Config.WHEEL_TOKEN_COST:
                return jsonify({"ok": False, "error": "No spins available. Earn more tokens!"}), 200
            user.wheel_tokens -= Config.WHEEL_TOKEN_COST

        reward = spin_wheel(user, rewards)
        user.last_wheel_spin_at = now

        ws = WheelSpin(user_id=user.id, reward_id=reward.id)
        s.add(ws)
        s.commit()

        response = {
            "ok": True,
            "reward": {
                "label": reward.label,
                "reward_type": reward.reward_type,
                "amount": reward.amount,
            },
        }
        response.update(serialize_user_state(user))
        return jsonify(response)


@app.get("/api/stickers")
def api_stickers():
    token = request.args.get("token")
    user = _get_user_from_token(token)
    if not user:
        abort(401)

    with Session() as s:
        user = s.merge(user)
        ensure_default_albums(s)
        albums = (
            s.query(StickerAlbum)
            .options(joinedload(StickerAlbum.stickers))
            .order_by(StickerAlbum.id)
            .all()
        )
        sticker_map = {
            (us.sticker_id, us.user_id): us
            for us in s.query(UserSticker).filter(UserSticker.user_id == user.id)
        }
        completions = {
            ac.album_id for ac in s.query(AlbumCompletion).filter(AlbumCompletion.user_id == user.id)
        }
        payload = []
        album_themes = {
            "ocean-legends": {
                "accent": "#00c2ff",
                "background": "/static/images/album-ocean.svg",
            },
            "sky-voyagers": {
                "accent": "#f48bff",
                "background": "/static/images/album-sky.svg",
            },
        }

        for album in albums:
            stickers = []
            owned = 0
            for sticker in album.stickers:
                owned_qty = sticker_map.get((sticker.id, user.id))
                qty = owned_qty.quantity if owned_qty else 0
                if qty:
                    owned += 1
                stickers.append(
                    {
                        "id": sticker.id,
                        "name": sticker.name,
                        "rarity": sticker.rarity,
                        "quantity": qty,
                        "image_url": sticker.image_url,
                    }
                )
            payload.append(
                {
                    "id": album.id,
                    "name": album.name,
                    "slug": album.slug,
                    "description": album.description,
                    "reward_spins": album.reward_spins,
                    "sticker_cost": album.sticker_cost,
                    "stickers": stickers,
                    "owned_count": owned,
                    "total": len(album.stickers),
                    "reward_claimed": album.id in completions,
                    "theme": album_themes.get(
                        album.slug,
                        {"accent": "#3dd5ff", "background": "/static/images/album-ocean.svg"},
                    ),
                }
            )
        duplicates = sum(
            max(us.quantity - 1, 0)
            for us in s.query(UserSticker).filter(UserSticker.user_id == user.id)
        )
        trade_sets = duplicates // Config.STICKER_TRADE_SET_SIZE if Config.STICKER_TRADE_SET_SIZE else 0
        return jsonify(
            {
                "ok": True,
                "albums": payload,
                "duplicates": duplicates,
                "trade": {
                    "set_size": Config.STICKER_TRADE_SET_SIZE,
                    "coins": Config.STICKER_TRADE_COINS,
                    "energy": Config.STICKER_TRADE_ENERGY,
                    "sets_available": trade_sets,
                },
                **serialize_user_state(user),
            }
        )


@app.post("/api/stickers/open")
def api_open_sticker_pack():
    payload = request.get_json(force=True)
    token = payload.get("token")
    album_id = payload.get("album_id")
    user = _get_user_from_token(token)
    if not user:
        abort(401)

    with Session() as s:
        user = s.merge(user)
        album = s.get(StickerAlbum, album_id)
        if not album:
            return jsonify({"ok": False, "error": "Album not found"}), 200
        if user.free_sticker_packs > 0:
            user.free_sticker_packs -= 1
        elif user.coins >= album.sticker_cost:
            user.coins -= album.sticker_cost
        else:
            return jsonify({"ok": False, "error": "Not enough SharkCoins or pack tokens"}), 200

        selected = pull_sticker(s, user, album)
        sticker_info = grant_sticker(s, user, selected)
        s.flush()

        response = {
            "ok": True,
            "sticker": {
                "name": sticker_info["sticker"].name,
                "rarity": sticker_info["sticker"].rarity,
                "quantity": sticker_info["quantity"],
                "album_completed": sticker_info["album_completed"],
            },
        }
        response.update(serialize_user_state(user))
        response["album_rewarded"] = False
        if sticker_info["album_completed"]:
            rewarded = complete_album(s, user, album)
            if rewarded:
                s.commit()
                response.update(serialize_user_state(user))
                response["album_rewarded"] = True
        s.commit()
        return jsonify(response)


@app.post("/api/stickers/trade")
def api_trade_stickers():
    payload = request.get_json(force=True)
    token = payload.get("token")
    reward_type = payload.get("reward_type", "coins")
    sets = int(payload.get("sets", 1))
    user = _get_user_from_token(token)
    if not user:
        abort(401)

    with Session() as s:
        user = s.merge(user)
        ok, msg, reward_payload = trade_stickers_for_reward(s, user, reward_type, sets)
        if not ok:
            s.rollback()
            return jsonify({"ok": False, "error": msg}), 200
        s.commit()
        response = {"ok": True, "reward": reward_payload, "message": msg}
        response.update(serialize_user_state(user))
        return jsonify(response)


@app.get("/api/events")
def api_events():
    token = request.args.get("token")
    user = _get_user_from_token(token)
    if not user:
        abort(401)

    with Session() as s:
        user = s.merge(user)
        ensure_demo_event(s)
        events = s.query(LiveEvent).order_by(LiveEvent.start_at).all()
        progress_map = {
            ep.event_id: ep
            for ep in s.query(EventProgress).filter(EventProgress.user_id == user.id)
        }
        payload = [serialize_event(evt, progress_map.get(evt.id)) for evt in events]
        return jsonify({"ok": True, "events": payload, **serialize_user_state(user)})


@app.get("/api/daily")
def api_daily_overview():
    token = request.args.get("token")
    user = _get_user_from_token(token)
    if not user:
        abort(401)
    return jsonify({"ok": True, "daily": _daily_summary(user), **serialize_user_state(user)})


@app.post("/api/daily/claim")
def api_daily_claim():
    payload = request.get_json(force=True)
    token = payload.get("token")
    user = _get_user_from_token(token)
    if not user:
        abort(401)

    now = datetime.utcnow()
    with Session() as s:
        user = s.merge(user)
        if user.last_daily_claim_at and now - user.last_daily_claim_at < timedelta(hours=20):
            return jsonify({"ok": False, "error": "Daily reward not ready yet"}), 200

        if user.last_daily_claim_at and now - user.last_daily_claim_at > timedelta(hours=36):
            user.daily_streak = 0

        user.daily_streak += 1
        user.last_daily_claim_at = now

        reward = _daily_reward_for_day(user.daily_streak)
        user.coins += reward["coins"]
        user.energy += reward["energy"]
        streak_bonus = reward["bonus_energy"]
        if streak_bonus:
            user.energy += streak_bonus
        if reward["wheel_tokens"]:
            user.wheel_tokens += reward["wheel_tokens"]
        if reward["sticker_packs"]:
            user.free_sticker_packs += reward["sticker_packs"]

        s.commit()
        payload = {
            "ok": True,
            "reward": reward,
            "streak_bonus": streak_bonus,
        }
        payload.update(serialize_user_state(user))
        return jsonify(payload)


@app.get("/api/leaderboard")
def api_leaderboard():
    token = request.args.get("token")
    user = _get_user_from_token(token)
    if not user:
        abort(401)

    with Session() as s:
        top_coins = (
            s.query(User.username, User.coins, User.level)
            .order_by(User.coins.desc())
            .limit(Config.LEADERBOARD_SIZE)
            .all()
        )
        top_xp = (
            s.query(User.username, User.xp, User.level)
            .order_by(User.xp.desc())
            .limit(Config.LEADERBOARD_SIZE)
            .all()
        )
        leaderboard = {
            "coins": [
                {"username": name or "Player", "coins": coins, "level": level}
                for name, coins, level in top_coins
            ],
            "xp": [
                {"username": name or "Player", "xp": xp, "level": level}
                for name, xp, level in top_xp
            ],
        }
        return jsonify({"ok": True, "leaderboard": leaderboard, **serialize_user_state(user)})


@app.get("/api/store")
def api_store():
    token = request.args.get("token")
    user = _get_user_from_token(token)
    if not user:
        abort(401)

    return jsonify({"ok": True, "star_packages": Config.STAR_PACKAGES, **serialize_user_state(user)})


@app.post("/api/store/purchase")
def api_store_purchase():
    payload = request.get_json(force=True)
    token = payload.get("token")
    pack_id = payload.get("pack_id")
    user = _get_user_from_token(token)
    if not user:
        abort(401)

    pack = next((p for p in Config.STAR_PACKAGES if p["id"] == pack_id), None)
    if not pack:
        return jsonify({"ok": False, "error": "Pack unavailable."}), 200

    with Session() as s:
        user = s.merge(user)
        user.energy += pack["energy"]
        bonus_tokens = pack.get("bonus_spins", 0)
        if bonus_tokens:
            user.wheel_tokens += bonus_tokens
        reference = f"WEBAPP-{datetime.utcnow().timestamp():.0f}-{pack_id}"
        payment = Payment(
            tg_payment_charge_id=reference,
            payload=pack_id,
            stars_amount=pack.get("stars", 0),
            user_id=user.id,
        )
        s.add(payment)
        s.commit()
        response = {"ok": True, "pack": pack}
        response.update(serialize_user_state(user))
        return jsonify(response)


@app.get("/api/glossary")
def api_glossary():
    token = request.args.get("token")
    user = _get_user_from_token(token)
    if not user:
        abort(401)

    glossary = [
        {
            "title": "Spins",
            "emoji": "🎰",
            "body": "Spend energy to fire the SharkSlot and earn SharkCoins + XP.",
            "details": [
                "Each multiplier adds the same energy cost but multiplies wins.",
                "Big wins trigger neon celebrations and boost level progress.",
                "Every spin records lifetime stats that appear on the leaderboard.",
            ],
            "image_url": "/static/images/info-spins.svg",
        },
        {
            "title": "Wheel of Tides",
            "emoji": "🌀",
            "body": "Use wheel tokens or cooldown spins to land jackpots, energy bursts, or sticker packs.",
            "details": [
                "A free spin unlocks every {hours} hours.".format(hours=Config.WHEEL_COOLDOWN_HOURS),
                "Tokens drop from level rewards, albums, and daily streak milestones.",
                "Every spin is logged so admins can audit wins via the database.",
            ],
            "image_url": "/static/images/info-wheel.svg",
        },
        {
            "title": "Sticker Albums",
            "emoji": "📔",
            "body": "Complete themed sticker sets to bank bonus spins and energy reserves.",
            "details": [
                "Ocean Legends and Sky Voyagers each feature unique art pieces.",
                "Duplicate stickers can be recycled for coins or energy trades.",
                "Album progress is saved forever—finishing re-activates rewards automatically.",
            ],
            "image_url": "/static/images/info-album.svg",
        },
        {
            "title": "Sticker Trades",
            "emoji": "🔁",
            "body": "Five duplicate stickers form a trade set that can be swapped for currency boosts.",
            "details": [
                f"Each set pays {Config.STICKER_TRADE_COINS} SharkCoins or {Config.STICKER_TRADE_ENERGY} Energy.",
                "Trades never consume your final copy—only extras beyond one of each design.",
                "Batch trades are supported from the mini app UI and admin endpoints.",
            ],
            "image_url": "/static/images/info-trade.svg",
        },
        {
            "title": "Energy",
            "emoji": "⚡",
            "body": "Energy fuels spins, wheel rewards, and album unlocks.",
            "details": [
                "Regenerates via daily streaks, level rewards, events, and Star Shop bundles.",
                "Wheel rewards labelled as spins convert to direct energy boosts.",
                "Admins can grant energy directly using reward links for support cases.",
            ],
            "image_url": "/static/images/info-energy.svg",
        },
        {
            "title": "SharkCoins",
            "emoji": "🪙",
            "body": "Primary currency for sticker packs, upgrades, and bragging rights.",
            "details": [
                "Earn coins from slots, wheel rewards, album completions, and trades.",
                "Leaderboard rankings showcase the richest divers in the reef.",
                "Admins can issue coin grants via /reward or the REST reward-link endpoint.",
            ],
            "image_url": "/static/images/info-coins.svg",
        },
        {
            "title": "Daily Streaks",
            "emoji": "📅",
            "body": "Log in every 20 hours to keep your streak alive and supercharge payouts.",
            "details": [
                "Seven-day streaks unlock bonus energy, wheel tokens, and sticker packs.",
                "Missing 36 hours resets progress—admins can reset manually for support.",
                "Upcoming milestone rewards are previewed inside the mini app daily card.",
            ],
            "image_url": "/static/images/info-daily.svg",
        },
        {
            "title": "Level Rewards",
            "emoji": "📈",
            "body": "XP from spins levels you up and unlocks milestone prize crates.",
            "details": [
                "Rewards include coins, energy, wheel tokens, spins, and legendary stickers.",
                "Level progress is visualized with neon progress bars and reward previews.",
                "Admins can inspect thresholds in config.py or award XP manually via SQL.",
            ],
            "image_url": "/static/images/info-level.svg",
        },
        {
            "title": "Leaderboards",
            "emoji": "🏆",
            "body": "Separate boards track top SharkCoins and XP divers in real time.",
            "details": [
                "Updated after every spin, wheel win, and album completion.",
                "Entries display usernames, holdings, and current level for context.",
                "Admins can extend leaderboard size via `LEADERBOARD_SIZE`.",
            ],
            "image_url": "/static/images/info-leaderboard.svg",
        },
        {
            "title": "Star Shop",
            "emoji": "⭐",
            "body": "Purchase energy + wheel bundles inside the mini app Star Market with instant delivery.",
            "details": [
                "Seven themed packs range from Coral Splash to Orbital Riptide and beyond.",
                "Every checkout happens in the web app and credits energy + tokens immediately.",
                "Purchases are logged in the payments table with `WEBAPP` references for audits.",
            ],
            "image_url": "/static/images/info-starshop.svg",
        },
        {
            "title": "Help & Guides",
            "emoji": "🧭",
            "body": "Use the Help dock in-app to revisit tutorials, feature explainers, and pro tips.",
            "details": [
                "The user guide cards break every system into quick steps for players.",
                "Admins can edit the markdown file `USER_GUIDE.md` to refresh copy instantly.",
                "Taskbar anchors jump straight to shop, spins, albums, wheel, and help panels.",
            ],
            "image_url": "/static/images/info-guide.svg",
        },
    ]

    return jsonify({"ok": True, "glossary": glossary, **serialize_user_state(user)})


@app.get("/api/guide")
def api_user_guide():
    token = request.args.get("token")
    user = _get_user_from_token(token)
    if not user:
        abort(401)

    guide = [
        {
            "emoji": "🚀",
            "title": "Dive In",
            "summary": "Launch SharkSpin, review your stats, and bookmark the taskbar shortcuts.",
            "steps": [
                "Tap the bottom taskbar to swap between Spins, Wheel, Albums, Shop, and Help.",
                "Check the hero stats card for Coins, Energy, Wheel Tokens, and Pack Tokens.",
                "Claim the Daily Dive reward before spinning to keep streak momentum alive.",
            ],
        },
        {
            "emoji": "🎰",
            "title": "Slot Machine Tips",
            "summary": "Energy powers the slot reels; match icons to earn coins, energy, and wheel tokens.",
            "steps": [
                "Choose a multiplier under the reels to increase both cost and payouts in lockstep.",
                "Watch for 🦈 wild surges—they combine with the other tiles for hybrid rewards.",
                "Progress bars above the reels update XP and level rewards in real time.",
            ],
        },
        {
            "emoji": "🌀",
            "title": "Wheel of Tides",
            "summary": "Spend wheel tokens or wait for cooldown spins to chase jackpot slices.",
            "steps": [
                "Tokens drop from streaks, albums, level milestones, and slot surges.",
                "Each segment shows color-coded loot; edit weights and colors inside the admin guide.",
                "Wheel history is logged so you can reconcile major wins during audits.",
            ],
        },
        {
            "emoji": "📔",
            "title": "Albums & Trades",
            "summary": "Open sticker packs, fill albums, and cash duplicates for energy or SharkCoins.",
            "steps": [
                "Albums preview remaining stickers and reward thresholds for completion.",
                "Use the trade buttons to convert duplicates in bundles of five or fifteen.",
                "Album completion auto-grants spins and energy—track history in the admin dashboard.",
            ],
        },
        {
            "emoji": "⭐",
            "title": "Shopping",
            "summary": "Purchase Star bundles directly in the mini app—grants are instant and logged.",
            "steps": [
                "Browse the Star Market for art-rich packages matched to campaign tiers.",
                "Confirm purchases to receive energy and wheel tokens immediately in-app.",
                "Admins can add, remove, or reorder packs via `Config.STAR_PACKAGES`.",
            ],
        },
    ]

    return jsonify({"ok": True, "guide": guide, **serialize_user_state(user)})


@app.post("/api/admin/reward-link")
def api_admin_reward_link():
    payload = request.get_json(force=True)
    admin_secret = payload.get("admin_secret")
    if admin_secret != Config.ADMIN_SECRET:
        abort(403)

    reward_type = payload.get("reward_type", "coins")
    amount = int(payload.get("amount", 100))
    uses = int(payload.get("uses", 1))
    creator = payload.get("created_by", "api")

    token = reward_signer.dumps({"type": reward_type, "amount": amount})

    with Session() as s:
        existing = (
            s.execute(select(RewardLink).where(RewardLink.token == token)).scalar_one_or_none()
        )
        if existing:
            reward_link = existing
            reward_link.reward_type = reward_type
            reward_link.amount = amount
            reward_link.uses_left = uses
            reward_link.is_active = True
            reward_link.created_by = creator
        else:
            reward_link = RewardLink(
                token=token,
                reward_type=reward_type,
                amount=amount,
                uses_left=uses,
                created_by=creator,
            )
            s.add(reward_link)
        s.commit()

    bot_username = payload.get("bot_username", "sharkspin_bot")
    url = f"https://t.me/{bot_username}/startapp?startapp=redeem_{token}"
    summary = f"+{amount} {reward_type.replace('_', ' ')}"
    return jsonify(
        {
            "ok": True,
            "token": token,
            "reward_url": url,
            "uses": uses,
            "summary": summary,
        }
    )


if __name__ == "__main__":
    app.run(debug=True)
