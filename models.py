from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float, Boolean
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
