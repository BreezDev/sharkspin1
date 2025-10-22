from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from flask import (
    Blueprint,
    abort,
    current_app,
    jsonify,
    render_template,
    request,
)
from itsdangerous import URLSafeSerializer
from sqlalchemy import func

from config import Config
from game_logic import (
    ensure_default_shop_items,
    ensure_default_slot_symbols,
    ensure_default_wheel_rewards,
    refresh_level,
)
from models import (
    BroadcastMessage,
    LiveEvent,
    RewardLink,
    ShopItem,
    SlotSymbol,
    User,
    WheelReward,
)

admin_bp = Blueprint("adminpanel", __name__, url_prefix="/admin")
reward_signer = URLSafeSerializer(Config.SECRET_KEY, salt="sharkspin:reward")


def _session():
    factory = current_app.config.get("SESSION_FACTORY")
    if factory is None:
        raise RuntimeError("Session factory not configured")
    return factory()


def _require_secret() -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    if request.method in ("POST", "PUT", "PATCH"):
        payload = request.get_json(silent=True) or {}
    header_secret = request.headers.get("X-Admin-Secret")
    query_secret = request.args.get("secret")
    body_secret = payload.get("secret") if isinstance(payload, dict) else None
    secret = header_secret or body_secret or query_secret
    if secret != Config.ADMIN_SECRET:
        abort(403)
    if isinstance(payload, dict):
        payload.pop("secret", None)
    return payload if isinstance(payload, dict) else {}


def _serialize_symbol(symbol: SlotSymbol) -> Dict[str, Any]:
    return {
        "id": symbol.id,
        "emoji": symbol.emoji,
        "name": symbol.name,
        "description": symbol.description,
        "weight": symbol.weight,
        "coins": symbol.coins,
        "energy": symbol.energy,
        "wheel_tokens": symbol.wheel_tokens,
        "art_url": symbol.art_url,
        "color": symbol.color,
        "is_enabled": symbol.is_enabled,
        "sort_order": symbol.sort_order,
    }


def _serialize_reward(reward: WheelReward) -> Dict[str, Any]:
    return {
        "id": reward.id,
        "label": reward.label,
        "reward_type": reward.reward_type,
        "amount": reward.amount,
        "weight": reward.weight,
        "color": reward.color,
    }


def _serialize_event(event: LiveEvent) -> Dict[str, Any]:
    return {
        "id": event.id,
        "slug": event.slug,
        "name": event.name,
        "description": event.description,
        "event_type": event.event_type,
        "start_at": event.start_at.isoformat(),
        "end_at": event.end_at.isoformat(),
        "target_spins": event.target_spins,
        "reward_type": event.reward_type,
        "reward_amount": event.reward_amount,
        "banner_url": event.banner_url,
    }


def _serialize_shop_item(item: ShopItem) -> Dict[str, Any]:
    return {
        "id": item.id,
        "slug": item.slug,
        "name": item.name,
        "stars": item.stars,
        "energy": item.energy,
        "bonus_spins": item.bonus_spins,
        "description": item.description,
        "art_url": item.art_url,
        "is_active": item.is_active,
        "sort_order": item.sort_order,
    }


def _serialize_link(link: RewardLink) -> Dict[str, Any]:
    return {
        "id": link.id,
        "token": link.token,
        "reward_type": link.reward_type,
        "amount": link.amount,
        "uses_left": link.uses_left,
        "is_active": link.is_active,
        "title": link.title,
        "note": link.note,
        "created_at": link.created_at.isoformat(),
    }


def _serialize_broadcast(broadcast: BroadcastMessage) -> Dict[str, Any]:
    return {
        "id": broadcast.id,
        "title": broadcast.title,
        "body": broadcast.body,
        "reward_url": broadcast.reward_url,
        "created_at": broadcast.created_at.isoformat(),
        "created_by": broadcast.created_by,
    }


@admin_bp.route("/")
def admin_home():
    return render_template("adminpanel.html")


@admin_bp.get("/api/overview")
def admin_overview():
    _require_secret()
    with _session() as session:
        ensure_default_slot_symbols(session)
        ensure_default_wheel_rewards(session)
        ensure_default_shop_items(session)

        symbols = [_serialize_symbol(s) for s in session.query(SlotSymbol).order_by(SlotSymbol.sort_order.asc()).all()]
        wheel = [_serialize_reward(r) for r in session.query(WheelReward).order_by(WheelReward.id.asc()).all()]
        events = [_serialize_event(e) for e in session.query(LiveEvent).order_by(LiveEvent.start_at.desc()).all()]
        shop = [
            _serialize_shop_item(item)
            for item in session.query(ShopItem).order_by(ShopItem.sort_order.asc()).all()
        ]
        reward_links = [
            _serialize_link(link)
            for link in session.query(RewardLink).order_by(RewardLink.created_at.desc()).limit(25)
        ]
        broadcasts = [
            _serialize_broadcast(b)
            for b in session.query(BroadcastMessage).order_by(BroadcastMessage.created_at.desc()).limit(25)
        ]
        user_total = session.query(func.count(User.id)).scalar() or 0
        total_energy = session.query(func.sum(User.energy)).scalar() or 0
        total_coins = session.query(func.sum(User.coins)).scalar() or 0

        leaderboard = [
            {
                "username": user.username or f"Captain {user.id}",
                "weekly_coins": user.weekly_coins or 0,
                "level": user.level,
            }
            for user in session.query(User)
            .order_by(User.weekly_coins.desc())
            .limit(10)
            .all()
        ]

        return jsonify(
            {
                "ok": True,
                "symbols": symbols,
                "wheel_rewards": wheel,
                "events": events,
                "shop": shop,
                "reward_links": reward_links,
                "broadcasts": broadcasts,
                "stats": {
                    "users": user_total,
                    "energy": int(total_energy),
                    "coins": int(total_coins),
                },
                "leaderboard": leaderboard,
            }
        )


@admin_bp.post("/api/slot-symbols")
def admin_save_symbol():
    data = _require_secret()
    symbol_id = data.get("id")
    with _session() as session:
        ensure_default_slot_symbols(session)
        if symbol_id:
            symbol = session.get(SlotSymbol, symbol_id)
            if not symbol:
                return jsonify({"ok": False, "error": "Symbol not found"}), 404
        else:
            symbol = SlotSymbol(sort_order=data.get("sort_order") or 0)
            session.add(symbol)

        for field in ["emoji", "name", "description", "art_url", "color"]:
            if field in data:
                setattr(symbol, field, data[field])
        for field in ["coins", "energy", "wheel_tokens", "weight", "sort_order"]:
            if field in data and data[field] is not None:
                setattr(symbol, field, float(data[field]) if field == "weight" else int(data[field]))
        if "is_enabled" in data:
            symbol.is_enabled = bool(data["is_enabled"])

        session.commit()
        return jsonify({"ok": True, "symbol": _serialize_symbol(symbol)})


@admin_bp.delete("/api/slot-symbols/<int:symbol_id>")
def admin_delete_symbol(symbol_id: int):
    _require_secret()
    with _session() as session:
        symbol = session.get(SlotSymbol, symbol_id)
        if not symbol:
            return jsonify({"ok": False, "error": "Symbol not found"}), 404
        symbol.is_enabled = False
        session.commit()
        return jsonify({"ok": True})


@admin_bp.post("/api/wheel-rewards")
def admin_save_wheel_reward():
    data = _require_secret()
    reward_id = data.get("id")
    with _session() as session:
        ensure_default_wheel_rewards(session)
        if reward_id:
            reward = session.get(WheelReward, reward_id)
            if not reward:
                return jsonify({"ok": False, "error": "Wheel reward not found"}), 404
        else:
            reward = WheelReward()
            session.add(reward)

        for field in ["label", "reward_type", "color"]:
            if field in data:
                setattr(reward, field, data[field])
        if "amount" in data:
            reward.amount = int(data["amount"])
        if "weight" in data:
            reward.weight = float(data["weight"])

        session.commit()
        return jsonify({"ok": True, "reward": _serialize_reward(reward)})


@admin_bp.delete("/api/wheel-rewards/<int:reward_id>")
def admin_delete_wheel_reward(reward_id: int):
    _require_secret()
    with _session() as session:
        reward = session.get(WheelReward, reward_id)
        if not reward:
            return jsonify({"ok": False, "error": "Wheel reward not found"}), 404
        session.delete(reward)
        session.commit()
        return jsonify({"ok": True})


@admin_bp.post("/api/events")
def admin_save_event():
    data = _require_secret()
    event_id = data.get("id")
    with _session() as session:
        if event_id:
            event = session.get(LiveEvent, event_id)
            if not event:
                return jsonify({"ok": False, "error": "Event not found"}), 404
        else:
            event = LiveEvent(
                slug=data.get("slug") or f"event-{int(datetime.utcnow().timestamp())}",
                start_at=datetime.utcnow(),
                end_at=datetime.utcnow(),
            )
            session.add(event)

        for field in ["slug", "name", "description", "event_type", "banner_url"]:
            if field in data and data[field]:
                setattr(event, field, data[field])
        for field in ["target_spins", "reward_amount"]:
            if field in data and data[field] is not None:
                setattr(event, field, int(data[field]))
        if "reward_type" in data:
            event.reward_type = data["reward_type"]
        if "start_at" in data:
            event.start_at = datetime.fromisoformat(data["start_at"])
        if "end_at" in data:
            event.end_at = datetime.fromisoformat(data["end_at"])

        session.commit()
        return jsonify({"ok": True, "event": _serialize_event(event)})


@admin_bp.delete("/api/events/<int:event_id>")
def admin_delete_event(event_id: int):
    _require_secret()
    with _session() as session:
        event = session.get(LiveEvent, event_id)
        if not event:
            return jsonify({"ok": False, "error": "Event not found"}), 404
        session.delete(event)
        session.commit()
        return jsonify({"ok": True})


@admin_bp.post("/api/shop-items")
def admin_save_shop_item():
    data = _require_secret()
    item_id = data.get("id")
    with _session() as session:
        ensure_default_shop_items(session)
        if item_id:
            item = session.get(ShopItem, item_id)
            if not item:
                return jsonify({"ok": False, "error": "Shop item not found"}), 404
        else:
            item = ShopItem(slug=data.get("slug") or f"bundle-{int(datetime.utcnow().timestamp())}")
            session.add(item)

        for field in ["name", "slug", "description", "art_url"]:
            if field in data and data[field]:
                setattr(item, field, data[field])
        for field in ["stars", "energy", "bonus_spins", "sort_order"]:
            if field in data and data[field] is not None:
                setattr(item, field, int(data[field]))
        if "is_active" in data:
            item.is_active = bool(data["is_active"])

        session.commit()
        return jsonify({"ok": True, "item": _serialize_shop_item(item)})


@admin_bp.delete("/api/shop-items/<int:item_id>")
def admin_delete_shop_item(item_id: int):
    _require_secret()
    with _session() as session:
        item = session.get(ShopItem, item_id)
        if not item:
            return jsonify({"ok": False, "error": "Shop item not found"}), 404
        item.is_active = False
        session.commit()
        return jsonify({"ok": True})


@admin_bp.post("/api/reward-links")
def admin_create_reward_link():
    data = _require_secret()
    reward_type = data.get("reward_type")
    amount = int(data.get("amount", 0))
    uses = int(data.get("uses", 1))
    if amount <= 0:
        return jsonify({"ok": False, "error": "Amount must be greater than zero"}), 400
    if uses <= 0:
        return jsonify({"ok": False, "error": "Uses must be at least 1"}), 400
    if reward_type not in {"coins", "energy", "spins", "wheel_tokens", "sticker_pack"}:
        return jsonify({"ok": False, "error": "Invalid reward type"}), 400

    payload = {"type": reward_type, "amount": amount, "created": datetime.utcnow().isoformat()}
    token = reward_signer.dumps(payload)
    reward_url = f"{Config.WEBAPP_URL.rstrip('/')}/redeem/{token}"

    with _session() as session:
        existing = (
            session.query(RewardLink)
            .filter(RewardLink.token == token)
            .one_or_none()
        )
        if existing:
            return jsonify({"ok": False, "error": "Reward already exists"}), 409

        link = RewardLink(
            token=token,
            reward_type=reward_type,
            amount=amount,
            uses_left=uses,
            created_by=data.get("created_by", "admin"),
            title=data.get("title", ""),
            note=data.get("note", ""),
        )
        session.add(link)
        session.commit()

    return jsonify({"ok": True, "reward_url": reward_url, "token": token})


@admin_bp.post("/api/broadcasts")
def admin_create_broadcast():
    data = _require_secret()
    title = data.get("title")
    body = data.get("body")
    if not title or not body:
        return jsonify({"ok": False, "error": "Title and body are required"}), 400
    reward_url = data.get("reward_url", "")

    with _session() as session:
        broadcast = BroadcastMessage(
            title=title,
            body=body,
            reward_url=reward_url,
            created_by=data.get("created_by", "admin"),
        )
        session.add(broadcast)
        session.commit()

    return jsonify({"ok": True})


@admin_bp.post("/api/leaderboard/reward")
def admin_reward_leaderboard():
    data = _require_secret()
    reward_type = data.get("reward_type", "coins")
    amount = int(data.get("amount", 0))
    if amount <= 0:
        return jsonify({"ok": False, "error": "Amount must be positive"}), 400

    user_ids: Optional[Iterable[int]] = data.get("user_ids")
    top_n = int(data.get("top_n", 0))

    with _session() as session:
        query = session.query(User)
        recipients: List[User] = []
        if user_ids:
            recipients = query.filter(User.id.in_(list(user_ids))).all()
        elif top_n > 0:
            recipients = (
                query.order_by(User.weekly_coins.desc(), User.total_earned.desc())
                .limit(top_n)
                .all()
            )
        else:
            return jsonify({"ok": False, "error": "Provide user_ids or top_n"}), 400

        for user in recipients:
            if reward_type == "coins":
                user.coins += amount
                user.total_earned += amount
                user.weekly_coins = (user.weekly_coins or 0) + amount
                refresh_level(user)
            elif reward_type == "energy":
                user.energy += amount
            elif reward_type == "spins":
                user.energy += amount * Config.ENERGY_PER_SPIN
            elif reward_type == "wheel_tokens":
                user.wheel_tokens += amount

        session.commit()

    return jsonify({"ok": True, "rewarded": len(recipients)})


@admin_bp.post("/api/leaderboard/reset")
def admin_reset_leaderboard():
    _require_secret()
    with _session() as session:
        session.query(User).update({User.weekly_coins: 0})
        session.commit()
    return jsonify({"ok": True})
