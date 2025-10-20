from datetime import datetime, timedelta
from typing import Any, Dict

from flask import Flask, jsonify, request, render_template, abort
from sqlalchemy import select
from sqlalchemy.orm import joinedload, sessionmaker
from itsdangerous import URLSafeSerializer, BadSignature

from config import Config
from models import (
    AlbumCompletion,
    Base,
    EventProgress,
    LiveEvent,
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
    complete_album,
    ensure_default_albums,
    ensure_default_wheel_rewards,
    ensure_demo_event,
    grant_sticker,
    pull_sticker,
    record_event_spin,
    serialize_event,
    spin_wheel,
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
    return f"https://game-tofumochi.pythonanywhere.com/redeem/{token}"


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
        else:
            return render_template("redeem.html", message="❌ Invalid reward type.")

        rl.uses_left -= 1
        if rl.uses_left <= 0:
            rl.is_active = False

        s.commit()

        msg = f"🎁 You received {rl.amount} {rl.reward_type.capitalize()}! ({rl.uses_left} uses left)"
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


def serialize_user_state(user: User) -> Dict[str, Any]:
    return {
        "coins": user.coins,
        "energy": user.energy,
        "level": user.level,
        "wheel_tokens": user.wheel_tokens,
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
        ok, msg, payout, result_data = apply_spin(user, multiplier=multiplier)
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
        return jsonify({"ok": True, "albums": payload, **serialize_user_state(user)})


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


if __name__ == "__main__":
    app.run(debug=True)
