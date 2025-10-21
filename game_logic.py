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


SYMBOLS: Sequence[str] = ("🦈", "💎", "🪙", "🍋", "🎲", "🔱")
SYMBOL_WEIGHTS: Sequence[float] = (0.24, 0.16, 0.16, 0.22, 0.17, 0.05)

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


def apply_spin(user: User, multiplier: int = 1):
    ok, msg = can_spin(user, multiplier)
    if not ok:
        return False, msg, 0, {"symbols": ("🪙", "🪙", "🪙"), "label": "No Spin"}

    user.energy -= Config.ENERGY_PER_SPIN * multiplier

    reels = [roll_symbol() for _ in range(3)]
    payout, label = calc_payout(reels, multiplier)

    user.coins += payout
    user.total_earned += payout
    user.level = max(1, 1 + int((user.total_earned / 1200) ** 0.6))

    return True, "", payout, {"symbols": reels, "label": label}


def roll_symbol() -> str:
    return random.choices(SYMBOLS, SYMBOL_WEIGHTS)[0]


def calc_payout(reels: Sequence[str], mult: int) -> Tuple[int, str]:
    if reels[0] == reels[1] == reels[2]:
        return 600 * mult, "Triple Match"
    if len(set(reels)) == 2:
        return 75 * mult, "Double Match"
    if "🦈" in reels:
        return 10 * mult, "Shark Spot"
    return 5 * mult, "Lucky Swim"


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
        user.wheel_tokens += reward.amount
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
            Sticker(album_id=ocean_album.id, name="Great Hammerhead", rarity="rare", weight=0.8),
            Sticker(album_id=ocean_album.id, name="Tiger Shark", rarity="common", weight=2.5),
            Sticker(album_id=ocean_album.id, name="Goblin Shark", rarity="epic", weight=0.35),
            Sticker(album_id=ocean_album.id, name="Manta Ray", rarity="common", weight=2.0),
            Sticker(album_id=ocean_album.id, name="Whale Shark", rarity="legendary", weight=0.15),
            Sticker(album_id=sky_album.id, name="Storm Seagull", rarity="common", weight=2.7),
            Sticker(album_id=sky_album.id, name="Jetpack Penguin", rarity="rare", weight=0.9),
            Sticker(album_id=sky_album.id, name="Aurora Drake", rarity="legendary", weight=0.2),
            Sticker(album_id=sky_album.id, name="Sky Whale", rarity="epic", weight=0.35),
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
    }
