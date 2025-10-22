from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Float,
    Boolean,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    tg_user_id = Column(String, unique=True, index=True, nullable=False)
    username = Column(String)
    coins = Column(Integer, default=0)
    energy = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_spin_at = Column(DateTime)
    level = Column(Integer, default=1)
    total_earned = Column(Integer, default=0)
    wheel_tokens = Column(Integer, default=0)
    last_wheel_spin_at = Column(DateTime)
    weekly_coins = Column(Integer, default=0)

class Spin(Base):
    __tablename__ = "spins"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    delta_coins = Column(Integer, default=0)
    result = Column(String)  # e.g., "small_win", "jackpot", "miss"
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")

class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True)
    tg_payment_charge_id = Column(String, index=True)  # from SuccessfulPayment.telegram_payment_charge_id
    payload = Column(String)  # what we sold
    stars_amount = Column(Integer)  # Stars amount paid (smallest unit is 1 star)
    user_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)

class RewardLink(Base):
    __tablename__ = "reward_links"
    id = Column(Integer, primary_key=True)
    token = Column(String, unique=True, index=True)
    reward_type = Column(String)
    amount = Column(Integer)
    uses_left = Column(Integer)
    created_by = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    title = Column(String, default="")
    note = Column(String, default="")


class SlotSymbol(Base):
    __tablename__ = "slot_symbols"
    id = Column(Integer, primary_key=True)
    emoji = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    description = Column(String, default="")
    weight = Column(Float, default=1.0)
    coins = Column(Integer, default=0)
    energy = Column(Integer, default=0)
    wheel_tokens = Column(Integer, default=0)
    art_url = Column(String, default="")
    color = Column(String, default="#1de5a0")
    is_enabled = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)


class WheelReward(Base):
    __tablename__ = "wheel_rewards"
    id = Column(Integer, primary_key=True)
    label = Column(String, nullable=False)
    reward_type = Column(String, nullable=False)
    amount = Column(Integer, nullable=False)
    weight = Column(Float, default=1.0)
    color = Column(String, default="#00bcd4")


class WheelSpin(Base):
    __tablename__ = "wheel_spins"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    reward_id = Column(Integer, ForeignKey("wheel_rewards.id"))
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User")
    reward = relationship("WheelReward")


class StickerAlbum(Base):
    __tablename__ = "sticker_albums"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, nullable=False)
    description = Column(String, default="")
    reward_spins = Column(Integer, default=1)
    sticker_cost = Column(Integer, default=50)


class Sticker(Base):
    __tablename__ = "stickers"
    id = Column(Integer, primary_key=True)
    album_id = Column(Integer, ForeignKey("sticker_albums.id"), index=True)
    name = Column(String, nullable=False)
    rarity = Column(String, default="common")
    weight = Column(Float, default=1.0)

    album = relationship("StickerAlbum", backref="stickers")


class UserSticker(Base):
    __tablename__ = "user_stickers"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    sticker_id = Column(Integer, ForeignKey("stickers.id"), index=True)
    quantity = Column(Integer, default=0)

    __table_args__ = (UniqueConstraint("user_id", "sticker_id", name="uq_user_sticker"),)

    user = relationship("User")
    sticker = relationship("Sticker")


class LiveEvent(Base):
    __tablename__ = "live_events"
    id = Column(Integer, primary_key=True)
    slug = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    description = Column(String, default="")
    start_at = Column(DateTime, nullable=False)
    end_at = Column(DateTime, nullable=False)
    target_spins = Column(Integer, default=50)
    reward_type = Column(String, default="spins")
    reward_amount = Column(Integer, default=1)
    event_type = Column(String, default="live")
    banner_url = Column(String, default="")


class EventProgress(Base):
    __tablename__ = "event_progress"
    id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey("live_events.id"), index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    progress = Column(Integer, default=0)
    claimed = Column(Boolean, default=False)

    __table_args__ = (UniqueConstraint("event_id", "user_id", name="uq_event_progress"),)

    event = relationship("LiveEvent", backref="progress_entries")
    user = relationship("User")


class AlbumCompletion(Base):
    __tablename__ = "album_completions"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    album_id = Column(Integer, ForeignKey("sticker_albums.id"), index=True)
    completed_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("user_id", "album_id", name="uq_album_completion"),)

    user = relationship("User")


class DailyRewardState(Base):
    __tablename__ = "daily_reward_state"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, unique=True, nullable=False)
    last_claim_at = Column(DateTime)
    streak = Column(Integer, default=0)
    total_claims = Column(Integer, default=0)

    user = relationship("User")


class ShopItem(Base):
    __tablename__ = "shop_items"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    slug = Column(String, unique=True, nullable=False)
    stars = Column(Integer, default=0)
    energy = Column(Integer, default=0)
    bonus_spins = Column(Integer, default=0)
    description = Column(String, default="")
    art_url = Column(String, default="")
    is_active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)


class BroadcastMessage(Base):
    __tablename__ = "broadcast_messages"
    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    body = Column(String, nullable=False)
    reward_url = Column(String, default="")
    created_by = Column(String, default="system")
    created_at = Column(DateTime, default=datetime.utcnow)
