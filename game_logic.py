import random
from datetime import datetime, timedelta
from typing import Dict, List, Sequence, Tuple

from config import Config
from models import (
    AlbumCompletion,
    EventProgress,
    LiveEvent,
    Sticker,
    StickerAlbum,
    User,
    UserSticker,
    WheelReward,
)


SYMBOL_DEFINITIONS: Sequence[Tuple[str, float, Dict[str, int]]] = (
    ("🪙", 0.21, {"coins": 120}),
    ("⚡", 0.18, {"coins": 70, "energy": 22}),
    ("🌀", 0.14, {"coins": 55, "wheel_tokens": 1}),
    ("💎", 0.16, {"coins": 220, "energy": 8}),
    ("🦈", 0.13, {"coins": 150, "energy": 24, "wheel_tokens": 1}),
    ("🌊", 0.18, {"coins": 135, "energy": 12}),
)

SYMBOLS: Sequence[str] = tuple(sym for sym, _, _ in SYMBOL_DEFINITIONS)
SYMBOL_WEIGHTS: Sequence[float] = tuple(weight for _, weight, _ in SYMBOL_DEFINITIONS)
SYMBOL_REWARD_BASE: Dict[str, Dict[str, int]] = {
    sym: base for sym, _, base in SYMBOL_DEFINITIONS
}
SHARK_SYMBOL = "🦈"


# --- Slot Machine Logic ----------------------------------------------------

def can_spin(user: User, multiplier: int) -> Tuple[bool, str]:
    if multiplier < 1:
        return False, "Invalid multiplier"
    if user.energy < Config.ENERGY_PER_SPIN * multiplier:
        return False, "Not enough energy"
    return True, ""


def merge_rewards(*rewards: Dict[str, float]) -> Dict[str, int]:
    merged: Dict[str, float] = {}
    for reward in rewards:
        if not reward:
            continue
        for key, value in reward.items():
            merged[key] = merged.get(key, 0.0) + float(value)
    finalized: Dict[str, int] = {}
    for key, value in merged.items():
        scaled = int(round(value))
        if scaled:
            finalized[key] = scaled
    return finalized


def scale_reward(reward: Dict[str, int], factor: float) -> Dict[str, float]:
    return {key: value * factor for key, value in reward.items()}


def apply_spin(user: User, multiplier: int = 1):
    ok, msg = can_spin(user, multiplier)
    if not ok:
        return False, msg, 0, {"symbols": ("🪙", "🪙", "🪙"), "label": "No Spin"}

    user.energy -= Config.ENERGY_PER_SPIN * multiplier

    reels = [roll_symbol() for _ in range(3)]
    reward, label = calc_payout(reels, multiplier)

    coins_delta = reward.get("coins", 0)
    energy_bonus = reward.get("energy", 0)
    wheel_bonus = reward.get("wheel_tokens", 0)

    user.coins += coins_delta
    user.total_earned += coins_delta
    if energy_bonus:
        user.energy += energy_bonus
    if wheel_bonus:
        user.wheel_tokens += wheel_bonus

    xp_gain = calc_spin_xp(reward, multiplier)
    user.xp += xp_gain
    user.lifetime_spins += multiplier
    user.last_spin_at = datetime.utcnow()

    level_info = calculate_level_progress(user.xp)
    user.level = level_info["level"]

    return True, "", coins_delta, {
        "symbols": reels,
        "label": label,
        "xp_gain": xp_gain,
        "rewards": reward,
        "level_info": level_info,
    }


def roll_symbol() -> str:
    return random.choices(SYMBOLS, SYMBOL_WEIGHTS)[0]


def calc_payout(reels: Sequence[str], mult: int) -> Tuple[Dict[str, int], str]:
    counts = {sym: reels.count(sym) for sym in set(reels)}

    def ensure_coins(payload: Dict[str, int]) -> Dict[str, int]:
        if "coins" not in payload:
            payload = {**payload, "coins": 0}
        return payload

    if len(counts) == 1:
        sym = reels[0]
        reward = merge_rewards(scale_reward(SYMBOL_REWARD_BASE[sym], 3 * mult))
        return ensure_coins(reward), f"Triple {sym}"

    if 3 in counts.values():
        sym = max(counts, key=counts.get)
        reward = merge_rewards(scale_reward(SYMBOL_REWARD_BASE[sym], 3 * mult))
        return ensure_coins(reward), f"Triple {sym}"

    if 2 in counts.values():
        sym = max(counts, key=counts.get)
        base = SYMBOL_REWARD_BASE.get(sym, {"coins": 60})
        reward = merge_rewards(scale_reward(base, 1.75 * mult))
        if SHARK_SYMBOL in counts and sym != SHARK_SYMBOL:
            shark_bonus = scale_reward(SYMBOL_REWARD_BASE[SHARK_SYMBOL], 0.45 * mult)
            reward = merge_rewards(reward, shark_bonus)
        reward.setdefault("coins", 0)
        reward["coins"] += int(40 * mult)
        return ensure_coins(reward), f"Double {sym}"

    if SHARK_SYMBOL in counts:
        companion = [sym for sym in reels if sym != SHARK_SYMBOL]
        if companion:
            base = merge_rewards(*[SYMBOL_REWARD_BASE.get(sym, {"coins": 60}) for sym in companion])
        else:
            base = SYMBOL_REWARD_BASE[SHARK_SYMBOL]
        reward = merge_rewards(
            scale_reward(base, 1.2 * mult),
            scale_reward(SYMBOL_REWARD_BASE[SHARK_SYMBOL], 0.8 * mult),
            {"coins": 60 * mult, "energy": 6 * mult},
        )
        return ensure_coins(reward), "Wild Surge"

    base_mix = merge_rewards(*[SYMBOL_REWARD_BASE.get(sym, {"coins": 45}) for sym in reels])
    reward = merge_rewards(scale_reward(base_mix, 0.55 * mult), {"coins": 30 * mult})
    return ensure_coins(reward), "Cascade Mix"


def calc_spin_xp(reward: Dict[str, int], multiplier: int) -> int:
    coin_equiv = reward.get("coins", 0)
    coin_equiv += reward.get("energy", 0) * 4
    coin_equiv += reward.get("wheel_tokens", 0) * 160
    coin_equiv += reward.get("sticker_packs", 0) * 220
    base = 18 * multiplier
    bonus = min(160, max(6, coin_equiv // 5))
    return base + bonus


def xp_threshold_for_level(level: int) -> int:
    if level <= 1:
        return 0
    curve = Config.LEVEL_XP_CURVE
    if level <= len(curve):
        return curve[level - 1]
    extra_levels = level - len(curve)
    last = curve[-1]
    # Apply gentle quadratic growth for levels beyond predefined curve
    return last + extra_levels * 650 + (extra_levels * (extra_levels - 1) // 2) * 180


def calculate_level_progress(xp: int) -> Dict[str, int]:
    level = 1
    while xp >= xp_threshold_for_level(level + 1):
        level += 1

    current_floor = xp_threshold_for_level(level)
    next_level = level + 1
    next_floor = xp_threshold_for_level(next_level)
    progress = xp - current_floor
    required = max(1, next_floor - current_floor)
    pct = max(0, min(100, int((progress / required) * 100)))
    return {
        "level": level,
        "xp": xp,
        "progress": progress,
        "required": required,
        "progress_pct": pct,
        "next_level": next_level,
        "next_level_xp": next_floor,
    }


# --- Wheel Of Fortune ------------------------------------------------------

def ensure_default_wheel_rewards(session) -> List[WheelReward]:
    rewards = session.query(WheelReward).all()
    if rewards:
        return rewards
    defaults = [
        ("250 Coins", "coins", 250, 2.5, "#1de5a0"),
        ("+1 Spin", "spins", 1, 2.0, "#3dd5ff"),
        ("Mega 1000", "coins", 1000, 0.6, "#f9c74f"),
        ("Energy Burst", "energy", 50, 1.8, "#ff6f59"),
        ("Sticker Pack", "sticker_pack", 1, 2.1, "#c77dff"),
        ("Jackpot 5000", "coins", 5000, 0.25, "#ff477e"),
        ("Lucky 100", "coins", 100, 3.2, "#0096c7"),
        ("+3 Spins", "spins", 3, 0.9, "#9ef01a"),
    ]
    for label, rtype, amount, weight, color in defaults:
        rewards.append(
            WheelReward(label=label, reward_type=rtype, amount=amount, weight=weight, color=color)
        )
    session.add_all(rewards)
    session.commit()
    return rewards


def spin_wheel(user: User, rewards: Sequence[WheelReward]):
    weights = [max(r.weight, 0.01) for r in rewards]
    reward = random.choices(rewards, weights)[0]
    apply_reward(user, reward)
    return reward


def apply_reward(user: User, reward: WheelReward):
    if reward.reward_type == "coins":
        user.coins += reward.amount
    elif reward.reward_type == "spins":
        user.energy += reward.amount * Config.ENERGY_PER_SPIN
    elif reward.reward_type == "energy":
        user.energy += reward.amount
    elif reward.reward_type == "sticker_pack":
        user.free_sticker_packs += reward.amount
    else:
        user.coins += reward.amount


# --- Stickers --------------------------------------------------------------

def ensure_default_albums(session):
    albums = session.query(StickerAlbum).all()
    if albums:
        return albums

    ocean_album = StickerAlbum(
        name="Ocean Legends",
        slug="ocean-legends",
        description="Collect the fiercest predators of the seven seas",
        reward_spins=3,
        sticker_cost=40,
    )
    sky_album = StickerAlbum(
        name="Sky Voyagers",
        slug="sky-voyagers",
        description="Fly with aerial aces to earn extra spins",
        reward_spins=2,
        sticker_cost=30,
    )

    session.add_all([ocean_album, sky_album])
    session.flush()

    session.add_all(
        [
            Sticker(
                album_id=ocean_album.id,
                name="Great Hammerhead",
                rarity="rare",
                weight=0.8,
                image_url="/static/images/stickers/great-hammerhead.svg",
            ),
            Sticker(
                album_id=ocean_album.id,
                name="Tiger Shark",
                rarity="common",
                weight=2.5,
                image_url="/static/images/stickers/tiger-shark.svg",
            ),
            Sticker(
                album_id=ocean_album.id,
                name="Goblin Shark",
                rarity="epic",
                weight=0.35,
                image_url="/static/images/stickers/goblin-shark.svg",
            ),
            Sticker(
                album_id=ocean_album.id,
                name="Manta Ray",
                rarity="common",
                weight=2.0,
                image_url="/static/images/stickers/manta-ray.svg",
            ),
            Sticker(
                album_id=ocean_album.id,
                name="Whale Shark",
                rarity="legendary",
                weight=0.15,
                image_url="/static/images/stickers/whale-shark.svg",
            ),
            Sticker(
                album_id=sky_album.id,
                name="Storm Seagull",
                rarity="common",
                weight=2.7,
                image_url="/static/images/stickers/storm-seagull.svg",
            ),
            Sticker(
                album_id=sky_album.id,
                name="Jetpack Penguin",
                rarity="rare",
                weight=0.9,
                image_url="/static/images/stickers/jetpack-penguin.svg",
            ),
            Sticker(
                album_id=sky_album.id,
                name="Aurora Drake",
                rarity="legendary",
                weight=0.2,
                image_url="/static/images/stickers/aurora-drake.svg",
            ),
            Sticker(
                album_id=sky_album.id,
                name="Sky Whale",
                rarity="epic",
                weight=0.35,
                image_url="/static/images/stickers/sky-whale.svg",
            ),
        ]
    )
    session.commit()
    return session.query(StickerAlbum).all()


def pull_sticker(session, user: User, album: StickerAlbum) -> Sticker:
    stickers = album.stickers
    weights = [max(s.weight, 0.05) for s in stickers]
    return random.choices(stickers, weights)[0]


def grant_sticker(session, user: User, sticker: Sticker) -> Dict:
    record = (
        session.query(UserSticker)
        .filter(UserSticker.user_id == user.id, UserSticker.sticker_id == sticker.id)
        .one_or_none()
    )
    if record:
        record.quantity += 1
    else:
        record = UserSticker(user_id=user.id, sticker_id=sticker.id, quantity=1)
        session.add(record)
    session.flush()
    total_album = sum(
        r.quantity
        for r in session.query(UserSticker)
        .filter_by(user_id=user.id)
        .filter(UserSticker.sticker.has(album_id=sticker.album_id))
    )
    album_size = len(sticker.album.stickers)
    completed = all(
        session.query(UserSticker)
        .filter_by(user_id=user.id, sticker_id=s.id)
        .one_or_none()
        for s in sticker.album.stickers
    )
    return {
        "sticker": sticker,
        "quantity": record.quantity,
        "album_completed": bool(completed),
        "album_size": album_size,
        "album_total": total_album,
    }


def complete_album(session, user: User, album: StickerAlbum):
    already = (
        session.query(AlbumCompletion)
        .filter(AlbumCompletion.user_id == user.id, AlbumCompletion.album_id == album.id)
        .one_or_none()
    )
    if already:
        return False
    session.add(AlbumCompletion(user_id=user.id, album_id=album.id))
    user.energy += album.reward_spins * Config.ENERGY_PER_SPIN
    user.wheel_tokens += album.reward_spins
    return True


def trade_stickers_for_reward(
    session, user: User, reward_type: str, sets: int
) -> Tuple[bool, str, Dict[str, int]]:
    if sets < 1:
        return False, "You must trade at least one set.", {}

    needed = Config.STICKER_TRADE_SET_SIZE * sets
    owned_duplicates: List[UserSticker] = (
        session.query(UserSticker)
        .filter(UserSticker.user_id == user.id, UserSticker.quantity > 1)
        .all()
    )
    total_extra = sum(us.quantity - 1 for us in owned_duplicates)
    if total_extra < needed:
        return (
            False,
            f"Collect {needed} duplicate stickers to trade (you have {total_extra}).",
            {},
        )

    remaining = needed
    for entry in owned_duplicates:
        if remaining <= 0:
            break
        usable = min(entry.quantity - 1, remaining)
        entry.quantity -= usable
        remaining -= usable
    session.flush()

    payload = {}
    if reward_type == "coins":
        coins = Config.STICKER_TRADE_COINS * sets
        user.coins += coins
        payload = {"coins": coins}
    elif reward_type == "energy":
        energy = Config.STICKER_TRADE_ENERGY * sets
        user.energy += energy
        payload = {"energy": energy}
    else:
        return False, "Invalid reward type", {}

    return True, "Trade successful", payload


def get_level_reward(level: int):
    return Config.LEVEL_REWARDS.get(level)


def apply_level_reward(session, user: User, level: int) -> Dict[str, str] | None:
    reward = get_level_reward(level)
    if not reward:
        return None

    rtype = reward["type"]
    amount = reward.get("amount", 0)
    if rtype == "coins":
        user.coins += amount
        text = f"+{amount} SharkCoins"
    elif rtype == "energy":
        user.energy += amount
        text = f"+{amount} Energy"
    elif rtype == "wheel_tokens":
        user.wheel_tokens += amount
        text = f"+{amount} Wheel Tokens"
    elif rtype == "spins":
        user.energy += amount * Config.ENERGY_PER_SPIN
        text = f"Free spins worth {amount * Config.ENERGY_PER_SPIN} energy"
    elif rtype == "sticker_pack":
        user.free_sticker_packs += amount
        text = f"+{amount} Sticker Pack Token"
    elif rtype == "legendary_sticker":
        sticker = (
            session.query(Sticker)
            .filter(Sticker.rarity == "legendary")
            .order_by(Sticker.id)
            .first()
        )
        if sticker:
            grant_sticker(session, user, sticker)
            text = f"Legendary sticker: {sticker.name}!"
        else:
            user.coins += 1500
            text = "+1500 SharkCoins (legendary bonus)"
    else:
        user.coins += amount
        text = f"+{amount} SharkCoins"

    user.level_reward_checkpoint = max(user.level_reward_checkpoint, level)
    session.flush()
    return {"level": level, "description": text}


def resolve_level_rewards(session, user: User, previous_level: int) -> List[Dict[str, str]]:
    rewards = []
    if user.level <= previous_level:
        return rewards
    for lvl in range(previous_level + 1, user.level + 1):
        if lvl <= user.level_reward_checkpoint:
            continue
        reward = apply_level_reward(session, user, lvl)
        if reward:
            rewards.append(reward)
    return rewards


# --- Events ----------------------------------------------------------------

def ensure_demo_event(session):
    event = session.query(LiveEvent).filter_by(slug="grand-regatta").one_or_none()
    if event:
        return event

    now = datetime.utcnow()
    event = LiveEvent(
        slug="grand-regatta",
        name="Grand Regatta",
        description="Spin the reels to earn regatta tokens and cash-in spins",
        start_at=now - timedelta(days=1),
        end_at=now + timedelta(days=5),
        target_spins=150,
        reward_type="spins",
        reward_amount=5,
    )
    session.add(event)
    session.commit()
    return event


def record_event_spin(session, user: User, multiplier: int):
    event = ensure_demo_event(session)
    if not event:
        return
    progress = (
        session.query(EventProgress)
        .filter(EventProgress.event_id == event.id, EventProgress.user_id == user.id)
        .one_or_none()
    )
    if not progress:
        progress = EventProgress(event_id=event.id, user_id=user.id, progress=0, claimed=False)
        session.add(progress)
    progress.progress += multiplier
    if progress.progress >= event.target_spins and not progress.claimed:
        if event.reward_type == "spins":
            user.energy += event.reward_amount * Config.ENERGY_PER_SPIN
        elif event.reward_type == "coins":
            user.coins += event.reward_amount
        else:
            user.wheel_tokens += event.reward_amount
        progress.claimed = True
    session.flush()


def serialize_event(event: LiveEvent, progress: EventProgress | None):
    now = datetime.utcnow()
    status = "upcoming"
    if event.start_at <= now <= event.end_at:
        status = "live"
    elif now > event.end_at:
        status = "ended"
    reward_emoji = {
        "spins": "🎰",
        "coins": "🪙",
        "wheel_tokens": "🌀",
        "energy": "⚡",
    }.get(event.reward_type, "🎁")
    art_map = {
        "grand-regatta": "/static/images/event-regatta.svg",
    }
    return {
        "slug": event.slug,
        "name": event.name,
        "description": event.description,
        "start_at": event.start_at.isoformat(),
        "end_at": event.end_at.isoformat(),
        "target_spins": event.target_spins,
        "reward_type": event.reward_type,
        "reward_amount": event.reward_amount,
        "status": status,
        "progress": progress.progress if progress else 0,
        "claimed": progress.claimed if progress else False,
        "emoji": reward_emoji,
        "art_url": art_map.get(event.slug),
    }
