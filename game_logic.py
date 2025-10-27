import random
from collections import Counter
from datetime import datetime, timedelta
from typing import Dict, List, Sequence, Tuple

from config import Config
from models import (
    AlbumCompletion,
    EventProgress,
    LiveEvent,
    Sticker,
    StickerAlbum,
    ShopItem,
    SlotSymbol,
    User,
    UserSticker,
    WheelReward,
)


def xp_threshold(level_index: int) -> int:
    curve = Config.LEVEL_XP_CURVE
    if level_index <= 0:
        return 0
    if level_index < len(curve):
        return curve[level_index]
    extra_steps = level_index - (len(curve) - 1)
    return curve[-1] + max(extra_steps, 0) * Config.LEVEL_EXTRA_STEP


def level_from_xp(total_xp: int) -> int:
    xp = max(int(total_xp or 0), 0)
    level = 1
    while xp >= xp_threshold(level):
        level += 1
    return level


def refresh_level(user: User) -> None:
    user.level = level_from_xp(getattr(user, "total_earned", 0))

def ensure_default_slot_symbols(session) -> List[SlotSymbol]:
    symbols = (
        session.query(SlotSymbol)
        .filter(SlotSymbol.is_enabled.is_(True))
        .order_by(SlotSymbol.sort_order.asc(), SlotSymbol.id.asc())
        .all()
    )
    if symbols:
        return symbols

    defaults: Sequence[Tuple[str, str, str, float, Dict[str, int], str, str]] = (
        (
            "🌊",
            "Empty Net",
            "House keeps the haul — no reward on this catch",
            3.6,
            {"coins": 0, "energy": 0, "wheel_tokens": 0},
            "#1d4ed8",
            "/static/images/header-bg.svg",
        ),
        (
            "🪙",
            "Treasure Cache",
            "Coin drip that feeds XP without guaranteeing profit",
            1.4,
            {"coins": 140, "energy": 0, "wheel_tokens": 0},
            "#ffd447",
            "/static/images/seasonal-sticker.svg",
        ),
        (
            "🎁",
            "Mystery Cache",
            "Modest coins with almost no kickbacks",
            0.85,
            {"coins": 80, "energy": 0, "wheel_tokens": 0},
            "#facc15",
            "/static/images/seasonal-sticker.svg",
        ),
        (
            "💠",
            "Prism Vault",
            "Rare payout that dents the house edge",
            0.6,
            {"coins": 320, "energy": 0, "wheel_tokens": 0},
            "#f472b6",
            "/static/images/seasonal-wheel.svg",
        ),
        (
            "⚡",
            "Energy Surge",
            "Hard-to-find burst that keeps marathon sessions alive",
            0.35,
            {"coins": 30, "energy": 12, "wheel_tokens": 0},
            "#5cf1ff",
            "/static/images/seasonal-energy.svg",
        ),
        (
            "🌀",
            "Token Squall",
            "Wheel tokens for the truly lucky",
            0.22,
            {"coins": 40, "energy": 0, "wheel_tokens": 14},
            "#8b5cf6",
            "/static/images/seasonal-wheel.svg",
        ),
        (
            "🦈",
            "Shark Jackpot",
            "Signature pull with heavy house resistance",
            0.12,
            {"coins": 620, "energy": 6, "wheel_tokens": 20},
            "#22d3ee",
            "/static/images/hero-boinkers.svg",
        ),
    )

    created: List[SlotSymbol] = []
    for idx, (emoji, name, description, weight, rewards, color, art_url) in enumerate(defaults):
        created.append(
            SlotSymbol(
                emoji=emoji,
                name=name,
                description=description,
                weight=weight,
                coins=rewards.get("coins", 0),
                energy=rewards.get("energy", 0),
                wheel_tokens=rewards.get("wheel_tokens", 0),
                color=color,
                art_url=art_url,
                sort_order=idx,
                is_enabled=True,
            )
        )
    session.add_all(created)
    session.commit()
    return (
        session.query(SlotSymbol)
        .filter(SlotSymbol.is_enabled.is_(True))
        .order_by(SlotSymbol.sort_order.asc(), SlotSymbol.id.asc())
        .all()
    )


def ensure_default_shop_items(session) -> List[ShopItem]:
    items = (
        session.query(ShopItem)
        .filter(ShopItem.is_active.is_(True))
        .order_by(ShopItem.sort_order.asc(), ShopItem.id.asc())
        .all()
    )
    if items:
        return items

    defaults: Sequence[Tuple[str, str, int, int, int, str]] = (
        (
            "Coral Splash 100",
            "energy_100",
            50,
            100,
            1,
            "Starter burst to keep the reels humming.",
        ),
        (
            "Abyss Diver 250",
            "energy_250",
            120,
            250,
            3,
            "Big energy dive plus bonus Wheel Tokens.",
        ),
        (
            "Mega Reef 600",
            "energy_600",
            260,
            600,
            8,
            "Legendary boost with neon wheel fireworks.",
        ),
        (
            "Galactic Tide 1200",
            "energy_1200",
            520,
            1200,
            20,
            "Whale-sized stash plus stacks of spins.",
        ),
    )

    records: List[ShopItem] = []
    for idx, (name, slug, stars, energy, bonus_spins, description) in enumerate(defaults):
        records.append(
            ShopItem(
                name=name,
                slug=slug,
                stars=stars,
                energy=energy,
                bonus_spins=bonus_spins,
                description=description,
                art_url=f"/static/images/shop/{slug}.svg",
                sort_order=idx,
                is_active=True,
            )
        )
    session.add_all(records)
    session.commit()
    return (
        session.query(ShopItem)
        .filter(ShopItem.is_active.is_(True))
        .order_by(ShopItem.sort_order.asc(), ShopItem.id.asc())
        .all()
    )

# --- Slot Machine Logic ----------------------------------------------------

def can_spin(user: User, multiplier: int) -> Tuple[bool, str]:
    if multiplier < 1:
        return False, "Invalid multiplier"
    energy_cost = Config.ENERGY_PER_SPIN * multiplier
    coin_cost = Config.COIN_COST_PER_SPIN * multiplier
    if user.energy < energy_cost:
        return False, "Not enough energy"
    if user.coins < coin_cost:
        return False, "Not enough SharkCoins"
    return True, ""


def apply_spin(session, user: User, multiplier: int = 1):
    ok, msg = can_spin(user, multiplier)
    if not ok:
        return False, msg, 0, {"symbols": ("🪙", "🪙", "🪙"), "label": "No Spin", "rewards": {}}

    symbols = ensure_default_slot_symbols(session)
    if not symbols:
        return False, "Slot machine is offline — no symbols configured", 0, {
            "symbols": ("❌", "❌", "❌"),
            "label": "No Config",
            "rewards": {},
        }

    weights = [max(sym.weight, 0.01) for sym in symbols]
    rolled: List[SlotSymbol] = [random.choices(symbols, weights)[0] for _ in range(3)]
    reels = tuple(sym.emoji for sym in rolled)

    energy_cost = Config.ENERGY_PER_SPIN * multiplier
    coin_cost = Config.COIN_COST_PER_SPIN * multiplier

    user.energy -= energy_cost
    user.coins -= coin_cost

    rewards, label = calc_payout(rolled, multiplier)

    coins_delta = rewards.get("coins", 0)
    energy_delta = rewards.get("energy", 0)
    wheel_delta = rewards.get("wheel_tokens", 0)

    user.coins += coins_delta
    user.energy += energy_delta
    user.wheel_tokens += wheel_delta
    net_coins = coins_delta - coin_cost
    user.total_earned += max(coins_delta, 0)
    user.weekly_coins = max(0, (user.weekly_coins or 0) + net_coins)
    refresh_level(user)

    result_payload = {
        "symbols": reels,
        "label": label,
        "rewards": rewards,
        "coin_cost": coin_cost,
        "net_coins": net_coins,
        "energy_spent": energy_cost,
        "multiplier": multiplier,
    }

    return True, "", net_coins, result_payload


def calc_symbol_rewards(reels: Sequence[SlotSymbol]) -> Dict[str, int]:
    rewards = {"coins": 0, "energy": 0, "wheel_tokens": 0}
    for symbol in reels:
        rewards["coins"] += max(symbol.coins, 0)
        rewards["energy"] += max(symbol.energy, 0)
        rewards["wheel_tokens"] += max(symbol.wheel_tokens, 0)
    return rewards


def calc_payout(reels: Sequence[SlotSymbol], mult: int) -> Tuple[Dict[str, int], str]:
    counts = Counter(sym.emoji for sym in reels)
    base_rewards = calc_symbol_rewards(reels)
    reward_multiplier = mult
    label = "Cascade"

    if len(counts) == 1:
        label = f"Triple {reels[0].name}"
        reward_multiplier *= 3
    elif any(count == 2 for count in counts.values()):
        pair_symbol = next(sym for sym, count in counts.items() if count == 2)
        pair_name = next(sym.name for sym in reels if sym.emoji == pair_symbol)
        label = f"Twin {pair_name}"
        reward_multiplier *= 2
    elif any(sym.emoji == "🦈" for sym in reels):
        label = "Shark Resonance"
        reward_multiplier = int(reward_multiplier * 1.5)

    adjusted = {
        key: int(value * reward_multiplier)
        for key, value in base_rewards.items()
        if value
    }

    payouts = {}
    for key in ("coins", "energy", "wheel_tokens"):
        base_value = adjusted.get(key, 0)
        if key == "coins":
            scalar = Config.SPIN_PAYOUT_COINS_SCALAR
        elif key == "energy":
            scalar = Config.SPIN_PAYOUT_ENERGY_SCALAR
        else:
            scalar = Config.SPIN_PAYOUT_TOKEN_SCALAR
        scaled_value = int(base_value * scalar)
        if key != "coins" and base_value > 0 and scaled_value <= 0:
            scaled_value = 1
        payouts[key] = max(scaled_value, 0)

    total_reward = sum(payouts.values())
    if total_reward > 0 and random.random() < Config.SPIN_BRICK_CHANCE:
        return {"coins": 0, "energy": 0, "wheel_tokens": 0}, "House Edge"

    if total_reward == 0:
        label = "Empty Net"
    return payouts, label


# --- Wheel Of Fortune ------------------------------------------------------

def ensure_default_wheel_rewards(session) -> List[WheelReward]:
    rewards = session.query(WheelReward).all()
    if rewards:
        return rewards
    defaults = [
        ("House Favor 400", "coins", 400, 3.6, "#1de5a0"),
        ("Safe Return 900", "coins", 900, 1.4, "#3dd5ff"),
        ("Sticker Cache", "sticker_pack", 1, 0.7, "#c77dff"),
        ("Energy Drip", "energy", 8, 0.55, "#ff6f59"),
        ("Wheel Token", "wheel_tokens", 1, 0.35, "#8b5cf6"),
        ("Mega Surge 1500", "coins", 1500, 0.42, "#f9c74f"),
        ("Double Token", "wheel_tokens", 2, 0.18, "#7c3aed"),
        ("Jackpot 5000", "coins", 5000, 0.12, "#ff477e"),
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
        user.total_earned += reward.amount
        user.weekly_coins = max(0, (user.weekly_coins or 0) + reward.amount)
        refresh_level(user)
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


def ensure_signature_events(session) -> List[LiveEvent]:
    now = datetime.utcnow()
    upcoming = now + timedelta(days=2)
    week_out = now + timedelta(days=7)

    definitions = [
        {
            "slug": "grand-regatta",
            "name": "Grand Regatta",
            "description": "Spin the reels to push your crew around the neon track and bank bonus spins.",
            "start_at": now - timedelta(days=1),
            "end_at": week_out,
            "target_spins": 300,
            "reward_type": "spins",
            "reward_amount": 8,
            "event_type": "live",
            "banner_url": "/static/images/events/grand-regatta.svg",
        },
        {
            "slug": "abyssal-bounty",
            "name": "Abyssal Bounty Hunt",
            "description": "Collect SharkCoins during night runs to unlock progressive coin crates.",
            "start_at": now - timedelta(hours=6),
            "end_at": now + timedelta(days=2),
            "target_spins": 180,
            "reward_type": "coins",
            "reward_amount": 3200,
            "event_type": "limited",
            "banner_url": "/static/images/events/abyssal-bounty.svg",
        },
        {
            "slug": "turbine-frenzy",
            "name": "Turbine Frenzy Weekend",
            "description": "Charge the turbines with energy-heavy wagers to earn elite wheel tokens.",
            "start_at": upcoming,
            "end_at": upcoming + timedelta(days=3),
            "target_spins": 220,
            "reward_type": "wheel_tokens",
            "reward_amount": 6,
            "event_type": "seasonal",
            "banner_url": "/static/images/events/turbine-frenzy.svg",
        },
    ]

    events: List[LiveEvent] = []
    for data in definitions:
        event = session.query(LiveEvent).filter_by(slug=data["slug"]).one_or_none()
        if not event:
            event = LiveEvent(**data)
            session.add(event)
        else:
            for key, value in data.items():
                setattr(event, key, value)
        events.append(event)
    session.commit()
    return events


def record_event_spin(session, user: User, multiplier: int):
    events = ensure_signature_events(session)
    if not events:
        return
    for event in events:
        progress = (
            session.query(EventProgress)
            .filter(EventProgress.event_id == event.id, EventProgress.user_id == user.id)
            .one_or_none()
        )
        if not progress:
            progress = EventProgress(
                event_id=event.id, user_id=user.id, progress=0, claimed=False
            )
            session.add(progress)
        progress.progress += multiplier
        if progress.progress >= event.target_spins and not progress.claimed:
            if event.reward_type == "spins":
                user.energy += event.reward_amount * Config.ENERGY_PER_SPIN
            elif event.reward_type == "coins":
                user.coins += event.reward_amount
                user.total_earned += event.reward_amount
                user.weekly_coins = max(0, (user.weekly_coins or 0) + event.reward_amount)
                refresh_level(user)
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
        "event_type": event.event_type,
        "banner_url": event.banner_url,
        "status": status,
        "progress": progress.progress if progress else 0,
        "claimed": progress.claimed if progress else False,
    }
