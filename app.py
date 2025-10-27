import json
import random
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import requests
from flask import Flask, jsonify, request, render_template, abort
from sqlalchemy import select
from sqlalchemy.orm import joinedload, sessionmaker
from itsdangerous import URLSafeSerializer, BadSignature

from config import Config
from content import DASHBOARD_FACTS, GUIDE_SECTIONS, TASKBAR_LINKS
from models import (
    AlbumCompletion,
    Base,
    DailyRewardState,
    EventProgress,
    LiveEvent,
    RewardLink,
    ShopItem,
    Spin,
    StickerAlbum,
    User,
    UserSticker,
    WheelReward,
    WheelSpin,
)
from game_logic import (
    apply_spin,
    award_wheel_token,
    clamp_token_drop,
    complete_album,
    ensure_default_albums,
    ensure_default_shop_items,
    ensure_default_slot_symbols,
    ensure_default_wheel_rewards,
    ensure_signature_events,
    grant_sticker,
    pull_sticker,
    refresh_level,
    record_event_spin,
    serialize_event,
    xp_threshold,
    spin_wheel,
)

from sqlalchemy import create_engine

app = Flask(__name__)
app.config.from_object(Config)

engine = create_engine(Config.SQLALCHEMY_DATABASE_URI, future=True)
Session = sessionmaker(bind=engine, expire_on_commit=False, future=True)
Base.metadata.create_all(engine)
app.config["SESSION_FACTORY"] = Session

try:
    from adminpanel import admin_bp

    app.register_blueprint(admin_bp)
except Exception:
    admin_bp = None

# Sign mini app init data (optional – extra layer beyond Telegram WebApp initData)
signer = URLSafeSerializer(Config.SECRET_KEY, salt="sharkspin:webapp")
reward_signer = URLSafeSerializer(Config.SECRET_KEY, salt="sharkspin:reward")


def _level_progress(user: User) -> Dict[str, Any]:
    current_level = max(user.level, 1)
    floor = xp_threshold(current_level - 1)
    ceiling = xp_threshold(current_level)
    current_xp = getattr(user, "total_earned", 0)
    gained = max(0, current_xp - floor)
    span = max(1, ceiling - floor)
    percent = min(100, int((gained / span) * 100))
    return {
        "current_xp": current_xp,
        "floor": floor,
        "ceiling": ceiling,
        "remaining": max(0, ceiling - current_xp),
        "percent": percent,
    }


def _get_daily_state(session, user: User) -> DailyRewardState:
    state = (
        session.query(DailyRewardState)
        .filter(DailyRewardState.user_id == user.id)
        .one_or_none()
    )
    if not state:
        state = DailyRewardState(user_id=user.id, streak=0, total_claims=0)
        session.add(state)
        session.flush()
    return state


def _daily_reward_values(next_streak: int) -> Dict[str, int]:
    coins = Config.DAILY_REWARD_BASE_COINS + Config.DAILY_STREAK_BONUS * max(next_streak - 1, 0)
    energy = Config.DAILY_REWARD_BASE_ENERGY if next_streak % 4 == 0 else 0
    wheel_tokens = 1 if next_streak in Config.DAILY_MILESTONES else 0
    return {"coins": coins, "energy": energy, "wheel_tokens": wheel_tokens}


def serialize_daily_state(state: DailyRewardState) -> Dict[str, Any]:
    now = datetime.utcnow()
    next_streak = state.streak + 1
    reward_preview = _daily_reward_values(next_streak)
    reward_preview["wheel_tokens"] = clamp_token_drop(reward_preview.get("wheel_tokens", 0))
    if state.last_claim_at is None:
        can_claim = True
        seconds_until = 0
    else:
        diff = now - state.last_claim_at
        can_claim = diff >= timedelta(hours=24)
        seconds_until = max(0, int(86400 - diff.total_seconds())) if not can_claim else 0
    return {
        "streak": state.streak,
        "last_claim_at": state.last_claim_at.isoformat() if state.last_claim_at else None,
        "can_claim": can_claim,
        "seconds_until": seconds_until,
        "next_reward": reward_preview,
    }


def _find_package(package_id: str | None) -> Optional[Dict[str, Any]]:
    if not package_id:
        return None
    with Session() as s:
        item = (
            s.query(ShopItem)
            .filter(ShopItem.slug == package_id, ShopItem.is_active.is_(True))
            .one_or_none()
        )
        if not item:
            return None
        return {
            "id": item.slug,
            "name": item.name,
            "stars": item.stars,
            "energy": item.energy,
            "bonus_spins": clamp_token_drop(item.bonus_spins),
            "description": item.description,
            "art_url": item.art_url,
        }


def _build_invoice_link(package: Dict[str, Any]) -> Optional[str]:
    endpoint = f"https://api.telegram.org/bot{Config.TELEGRAM_BOT_TOKEN}/createInvoiceLink"
    payload = {
        "title": package["name"],
        "description": package.get("description", ""),
        "payload": package["id"],
        "currency": "XTR",
        "prices": json.dumps(
            [{"label": package["name"], "amount": int(package["stars"])}]
        ),
    }
    if package.get("art_url"):
        payload["photo_url"] = package["art_url"]

    try:
        response = requests.post(endpoint, data=payload, timeout=8)
    except requests.RequestException:
        return None

    if not response.ok:
        return None
    data = response.json()
    if not data.get("ok"):
        return None
    return data.get("result")


def _state_with_daily(session, user: User) -> Dict[str, Any]:
    payload = serialize_user_state(user)
    daily_state = _get_daily_state(session, user)
    payload["daily"] = serialize_daily_state(daily_state)
    return payload

@app.before_request
def bootstrap_catalogs():
    # Ensure default data exists before handling requests that need them
    with Session() as s:
        ensure_default_wheel_rewards(s)
        ensure_default_albums(s)
        ensure_signature_events(s)
        ensure_default_slot_symbols(s)
        ensure_default_shop_items(s)


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

        sticker_pull_summaries: list[str] = []
        albums_completed = 0

        if rl.reward_type == "coins":
            user.coins += rl.amount
            user.total_earned += rl.amount
            user.weekly_coins = max(0, (user.weekly_coins or 0) + rl.amount)
            refresh_level(user)
        elif rl.reward_type == "energy":
            user.energy += rl.amount
        elif rl.reward_type == "spins":
            user.energy += rl.amount * Config.ENERGY_PER_SPIN
        elif rl.reward_type == "wheel_tokens":
            award_wheel_token(user, rl.amount)
        elif rl.reward_type == "sticker_pack":
            ensure_default_albums(s)
            albums = (
                s.query(StickerAlbum)
                .options(joinedload(StickerAlbum.stickers))
                .order_by(StickerAlbum.id)
                .all()
            )
            if not albums:
                return render_template(
                    "redeem.html",
                    message="⚠️ No sticker albums are configured yet. Add albums before issuing sticker pack rewards.",
                )

            for _ in range(max(int(rl.amount), 0)):
                album = random.choice(albums)
                pulled = pull_sticker(s, user, album)
                sticker_info = grant_sticker(s, user, pulled)
                summary = f"{pulled.name} ({pulled.rarity}) from {album.name}"
                if sticker_info["album_completed"]:
                    if complete_album(s, user, album):
                        albums_completed += 1
                        summary += " — Album completed!"
                sticker_pull_summaries.append(summary)
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
            "wheel_tokens": "1 Wheel Token 🌀" if clamp_token_drop(rl.amount) else "No Wheel Tokens",
            "sticker_pack": f"{rl.amount} Sticker Packs 📔",
        }
        reward_text = reward_text_map.get(rl.reward_type, f"{rl.amount} {rl.reward_type}")
        remaining = max(rl.uses_left, 0)
        details = ""
        if sticker_pull_summaries:
            pulls = "; ".join(sticker_pull_summaries)
            details = f"\nOpened packs: {pulls}"
            if albums_completed:
                details += f"\nAlbums completed: {albums_completed}"
        msg = f"🎁 You received {reward_text}! ({remaining} uses left){details}"
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
        payload = _state_with_daily(s, user)
        payload.update({"ok": True, "token": token})
        return jsonify(payload)


def serialize_user_state(user: User) -> Dict[str, Any]:
    progress = _level_progress(user)
    return {
        "coins": user.coins,
        "energy": user.energy,
        "level": user.level,
        "wheel_tokens": user.wheel_tokens,
        "total_earned": getattr(user, "total_earned", 0),
        "weekly_coins": getattr(user, "weekly_coins", 0),
        "energy_per_spin": Config.ENERGY_PER_SPIN,
        "coin_cost_per_spin": Config.COIN_COST_PER_SPIN,
        "spin_multipliers": Config.SPIN_MULTIPLIER_PRESETS,
        "progress": progress,
        "last_wheel_spin_at": user.last_wheel_spin_at.isoformat()
        if user.last_wheel_spin_at
        else None,
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
        ok, msg, payout, result_data = apply_spin(s, user, multiplier=multiplier)
        if not ok:
            return jsonify({"ok": False, "error": msg}), 200
        rec = Spin(user_id=user.id, delta_coins=payout, result=result_data["label"])
        s.add(rec)
        record_event_spin(s, user, multiplier)
        s.commit()
        response = {
            "ok": True,
            "payout": payout,
            "result": result_data,
        }
        response.update(_state_with_daily(s, user))
        return jsonify(response)


@app.get("/api/me")
def api_me():
    token = request.args.get("token")
    user = _get_user_from_token(token)
    if not user:
        abort(401)
    with Session() as s:
        user = s.merge(user)
        payload = _state_with_daily(s, user)
        return jsonify({"ok": True, **payload})


@app.get("/api/daily")
def api_daily():
    token = request.args.get("token")
    user = _get_user_from_token(token)
    if not user:
        abort(401)
    with Session() as s:
        user = s.merge(user)
        state = _state_with_daily(s, user)
        state.update({"milestones": Config.DAILY_MILESTONES})
        return jsonify({"ok": True, **state})


@app.post("/api/daily/claim")
def api_daily_claim():
    payload = request.get_json(force=True)
    token = payload.get("token")
    user = _get_user_from_token(token)
    if not user:
        abort(401)

    with Session() as s:
        user = s.merge(user)
        state = _get_daily_state(s, user)
        now = datetime.utcnow()
        if state.last_claim_at and (now - state.last_claim_at) > timedelta(hours=48):
            state.streak = 0
        if state.last_claim_at and (now - state.last_claim_at) < timedelta(hours=24):
            return jsonify(
                {
                    "ok": False,
                    "error": "Daily reward already claimed. Come back later!",
                    "daily": serialize_daily_state(state),
                }
            ), 200

        reward = _daily_reward_values(state.streak + 1)
        user.coins += reward.get("coins", 0)
        user.energy += reward.get("energy", 0)
        token_award = clamp_token_drop(reward.get("wheel_tokens", 0))
        if token_award:
            award_wheel_token(user, token_award)
        reward["wheel_tokens"] = token_award
        if reward.get("coins"):
            user.total_earned += reward.get("coins", 0)
            user.weekly_coins = max(0, (user.weekly_coins or 0) + reward.get("coins", 0))
            refresh_level(user)

        state.streak += 1
        state.total_claims += 1
        state.last_claim_at = now

        response_state = _state_with_daily(s, user)
        response_state.update(
            {
                "ok": True,
                "reward": reward,
                "claimed_at": now.isoformat(),
                "milestones": Config.DAILY_MILESTONES,
            }
        )
        s.commit()
        return jsonify(response_state)


@app.get("/api/shop")
def api_shop():
    token = request.args.get("token")
    user = _get_user_from_token(token)
    if not user:
        abort(401)
    with Session() as s:
        user = s.merge(user)
        ensure_default_shop_items(s)
        packages = [
            {
                "id": item.slug,
                "name": item.name,
                "stars": item.stars,
                "energy": item.energy,
                "bonus_spins": clamp_token_drop(item.bonus_spins),
                "description": item.description,
                "art_url": item.art_url,
            }
            for item in s.query(ShopItem)
            .filter(ShopItem.is_active.is_(True))
            .order_by(ShopItem.sort_order.asc(), ShopItem.id.asc())
        ]
        state = _state_with_daily(s, user)
        state.update({"packages": packages})
        return jsonify({"ok": True, **state})


@app.post("/api/shop/order")
def api_shop_order():
    payload = request.get_json(force=True)
    token = payload.get("token")
    package_id = payload.get("package_id")
    user = _get_user_from_token(token)
    if not user:
        abort(401)

    package = _find_package(package_id)
    if not package:
        return jsonify({"ok": False, "error": "Package not found"}), 200

    invoice_url = _build_invoice_link(package)
    fallback = None
    if not invoice_url and Config.BOT_USERNAME:
        fallback = f"https://t.me/{Config.BOT_USERNAME}?start=buy_{package['id']}"

    response: Dict[str, Any] = {
        "ok": True,
        "package": {
            "id": package["id"],
            "name": package["name"],
            "stars": package["stars"],
            "energy": package["energy"],
            "bonus_spins": clamp_token_drop(package.get("bonus_spins", 0)),
        },
        "invoice_url": invoice_url,
        "fallback_url": fallback,
    }
    if not invoice_url:
        response["warning"] = "Invoice link could not be created automatically."
    return jsonify(response)


@app.get("/api/catalog")
def api_catalog():
    token = request.args.get("token")
    user = _get_user_from_token(token)
    if not user:
        abort(401)
    with Session() as s:
        user = s.merge(user)
        state = _state_with_daily(s, user)
        state.update(
            {
                "taskbar": TASKBAR_LINKS,
                "guide": GUIDE_SECTIONS,
                "callouts": DASHBOARD_FACTS,
            }
        )
        return jsonify({"ok": True, **state})


@app.get("/api/wheel")
def api_wheel_catalog():
    token = request.args.get("token")
    user = _get_user_from_token(token)
    if not user:
        abort(401)
    with Session() as s:
        user = s.merge(user)
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
        state = _state_with_daily(s, user)
        return jsonify({"ok": True, "rewards": data, **state})


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
        response.update(_state_with_daily(s, user))
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
                }
            )
        state = _state_with_daily(s, user)
        return jsonify({"ok": True, "albums": payload, **state})


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
        if user.coins < album.sticker_cost:
            return jsonify({"ok": False, "error": "Not enough SharkCoins"}), 200

        user.coins -= album.sticker_cost
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
        response.update(_state_with_daily(s, user))
        response["album_rewarded"] = False
        if sticker_info["album_completed"]:
            rewarded = complete_album(s, user, album)
            if rewarded:
                s.commit()
                response.update(_state_with_daily(s, user))
                response["album_rewarded"] = True
        s.commit()
        return jsonify(response)


@app.get("/api/events")
def api_events():
    token = request.args.get("token")
    user = _get_user_from_token(token)
    if not user:
        abort(401)

    with Session() as s:
        user = s.merge(user)
        ensure_signature_events(s)
        events = s.query(LiveEvent).order_by(LiveEvent.start_at).all()
        progress_map = {
            ep.event_id: ep
            for ep in s.query(EventProgress).filter(EventProgress.user_id == user.id)
        }
        payload = [serialize_event(evt, progress_map.get(evt.id)) for evt in events]
        state = _state_with_daily(s, user)
        return jsonify({"ok": True, "events": payload, **state})


@app.get("/api/leaderboard")
def api_leaderboard():
    token = request.args.get("token")
    user = _get_user_from_token(token)
    if not user:
        abort(401)

    with Session() as s:
        user = s.merge(user)
        top_players = (
            s.query(User)
            .order_by(User.weekly_coins.desc(), User.total_earned.desc())
            .limit(Config.LEADERBOARD_SIZE)
            .all()
        )
        leaders = [
            {
                "position": idx + 1,
                "user_id": p.id,
                "tg_user_id": p.tg_user_id,
                "username": p.username or f"Captain {p.id}",
                "weekly_coins": p.weekly_coins or 0,
                "level": p.level,
            }
            for idx, p in enumerate(top_players)
        ]

        my_rank = next((entry["position"] for entry in leaders if entry["user_id"] == user.id), None)

        return jsonify(
            {
                "ok": True,
                "leaders": leaders,
                "me": {
                    "position": my_rank,
                    "weekly_coins": user.weekly_coins or 0,
                    "level": user.level,
                },
            }
        )


if __name__ == "__main__":
    app.run(debug=True)
