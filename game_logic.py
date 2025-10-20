import random
from datetime import datetime, timedelta

from config import Config

REEL_TABLE = [
    ("miss", 0, 0.60),
    ("small_win", 5, 0.25),
    ("med_win", 20, 0.10),
    ("big_win", 100, 0.045),
    ("jackpot", 1000, 0.005),
]

# Precompute cumulative weights
CUM = []
acc = 0.0
for name, payout, p in REEL_TABLE:
    acc += p
    CUM.append((name, payout, acc))


def roll_once():
    r = random.random()
    for name, payout, c in CUM:
        if r <= c:
            return name, payout
    return REEL_TABLE[-1][0], REEL_TABLE[-1][1]


def can_spin(user, multiplier):
    if user.energy < Config.ENERGY_PER_SPIN * multiplier:
        return False, "Not enough energy"
    return True, None


def apply_spin(user, multiplier=1):
    ok, msg = can_spin(user, multiplier)
    if not ok:
        return False, msg, 0, "miss"

    # energy cost
    user.energy -= Config.ENERGY_PER_SPIN * multiplier

    # roll 3 symbols
    reels = [roll_symbol() for _ in range(3)]
    payout = calc_payout(reels, multiplier)

    user.coins += payout
    user.total_earned += payout
    user.level = 1 + int((user.total_earned / 1000) ** 0.5)

    return True, None, payout, reels

def roll_symbol():
    symbols = ["🦈","💎","🪙","🍋","🎲","🔱"]
    weights = [0.25,0.15,0.15,0.25,0.15,0.05]
    return random.choices(symbols, weights)[0]

def calc_payout(reels, mult):
    # e.g. 3 matching = jackpot
    if reels[0] == reels[1] == reels[2]:
        return 500 * mult
    elif reels[0] == reels[1] or reels[1] == reels[2] or reels[0] == reels[2]:
        return 50 * mult
    else:
        return 5 * mult