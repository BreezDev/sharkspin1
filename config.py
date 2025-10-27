import os

class Config:
    """Central configuration for SharkSpin."""

    # Flask / Database
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", "sqlite:////home/tofumochi/sharkspin/sharkspin.db"
    )
    SQLALCHEMY_ECHO = False

    # Web experience
    WEBAPP_URL = os.getenv("WEBAPP_URL", "https://game-tofumochi.pythonanywhere.com")

    # Telegram
    TELEGRAM_BOT_TOKEN = os.getenv(
        "TELEGRAM_BOT_TOKEN", "8220458714:AAHJeibywqHXQf1bJp0bQbvjpEO0gaLhQOM"
    )
    BOT_USERNAME = os.getenv("BOT_USERNAME", "SharkSpinBot")
    ADMIN_SECRET = os.getenv("ADMIN_SECRET", "super-shark-admin")

    # Game economy
    STARTING_COINS = int(os.getenv("STARTING_COINS", 250))
    STARTING_ENERGY = int(os.getenv("STARTING_ENERGY", 5))
    ENERGY_PER_SPIN = int(os.getenv("ENERGY_PER_SPIN", 3))
    COIN_COST_PER_SPIN = int(os.getenv("COIN_COST_PER_SPIN", 75))
    SPIN_COOLDOWN_MS = int(os.getenv("SPIN_COOLDOWN_MS", 900))
    SPIN_MULTIPLIER_PRESETS = [
        int(x)
        for x in os.getenv(
            "SPIN_MULTIPLIER_PRESETS",
            "1,2,5,10,20,50,100,250,500,750,1000,1500",
        ).split(",")
    ]

    DAILY_REWARD_BASE_COINS = int(os.getenv("DAILY_REWARD_BASE_COINS", 120))
    DAILY_REWARD_BASE_ENERGY = int(os.getenv("DAILY_REWARD_BASE_ENERGY", 1))
    DAILY_STREAK_BONUS = int(os.getenv("DAILY_STREAK_BONUS", 40))
    DAILY_MILESTONES = [int(x) for x in os.getenv("DAILY_MILESTONES", "7,14,21,28").split(",")]  # claim days to showcase

    LEVEL_XP_CURVE = [0, 600, 1600, 3200, 5200, 7800, 11000, 15000, 19500, 24500]
    LEVEL_EXTRA_STEP = int(os.getenv("LEVEL_EXTRA_STEP", 5000))
    LEVEL_REWARDS = {
        2: {"type": "coins", "amount": 400},
        3: {"type": "energy", "amount": 30},
        4: {"type": "wheel_tokens", "amount": 1},
        5: {"type": "sticker_pack", "amount": 1},
        6: {"type": "coins", "amount": 500},
        7: {"type": "energy", "amount": 50},
        8: {"type": "spins", "amount": 3},
        9: {"type": "coins", "amount": 1000},
        10: {"type": "legendary_sticker", "amount": 1},
    }

    # Sticker trading
    STICKER_TRADE_SET_SIZE = int(os.getenv("STICKER_TRADE_SET_SIZE", 5))
    STICKER_TRADE_COINS = int(os.getenv("STICKER_TRADE_COINS", 350))
    STICKER_TRADE_ENERGY = int(os.getenv("STICKER_TRADE_ENERGY", 18))

    # Wheel of fortune
    DAILY_FREE_WHEEL_SPINS = int(os.getenv("DAILY_FREE_WHEEL_SPINS", 0))
    WHEEL_COOLDOWN_HOURS = int(os.getenv("WHEEL_COOLDOWN_HOURS", 3))
    WHEEL_TOKEN_COST = int(os.getenv("WHEEL_TOKEN_COST", 1))

    # Leaderboard
    LEADERBOARD_SIZE = int(os.getenv("LEADERBOARD_SIZE", 50))

    # Spin balancing
    SPIN_PAYOUT_COINS_SCALAR = float(os.getenv("SPIN_PAYOUT_COINS_SCALAR", 0.45))
    SPIN_PAYOUT_ENERGY_SCALAR = float(os.getenv("SPIN_PAYOUT_ENERGY_SCALAR", 0.2))
    SPIN_PAYOUT_TOKEN_SCALAR = float(os.getenv("SPIN_PAYOUT_TOKEN_SCALAR", 0.08))
    SPIN_BRICK_CHANCE = float(os.getenv("SPIN_BRICK_CHANCE", 0.32))

    # Payments (Stars / XTR)
    STAR_PACKAGES = [
        {
            "id": os.getenv("STAR_PACK_1_ID", "energy_100"),
            "name": "+100 Energy",
            "stars": int(os.getenv("STAR_PACK_1_STARS", 50)),
            "energy": int(os.getenv("STAR_PACK_1_ENERGY", 100)),
            "bonus_spins": 0,
            "description": "Starter burst to keep the reels humming.",
            "art_url": "/static/images/star-pack-coral.svg",
        },
        {
            "id": os.getenv("STAR_PACK_2_ID", "energy_250"),
            "name": "+250 Energy",
            "stars": int(os.getenv("STAR_PACK_2_STARS", 120)),
            "energy": int(os.getenv("STAR_PACK_2_ENERGY", 250)),
            "bonus_spins": 0,
            "description": "Big energy dive plus bonus Wheel Tokens.",
            "art_url": "/static/images/star-pack-abyss.svg",
        },
        {
            "id": os.getenv("STAR_PACK_3_ID", "energy_600"),
            "name": "+600 Energy",
            "stars": int(os.getenv("STAR_PACK_3_STARS", 260)),
            "energy": int(os.getenv("STAR_PACK_3_ENERGY", 600)),
            "bonus_spins": 1,
            "description": "Legendary boost with neon wheel fireworks.",
            "art_url": "/static/images/star-pack-mega.svg",
        },
        {
            "id": os.getenv("STAR_PACK_4_ID", "energy_1200"),
            "name": "+1200 Energy",
            "stars": int(os.getenv("STAR_PACK_4_STARS", 520)),
            "energy": int(os.getenv("STAR_PACK_4_ENERGY", 1200)),
            "bonus_spins": 1,
            "description": "Whale-sized stash plus stacks of spins.",
            "art_url": "/static/images/star-pack-galaxy.svg",
        },
        {
            "id": os.getenv("STAR_PACK_5_ID", "energy_2500"),
            "name": "+2500 Energy",
            "stars": int(os.getenv("STAR_PACK_5_STARS", 980)),
            "energy": int(os.getenv("STAR_PACK_5_ENERGY", 2500)),
            "bonus_spins": 1,
            "description": "Ultimate marathon kit for leaderboard runs.",
            "art_url": "/static/images/star-pack-titan.svg",
        },
        {
            "id": os.getenv("STAR_PACK_6_ID", "energy_4200"),
            "name": "+4200 Energy",
            "stars": int(os.getenv("STAR_PACK_6_STARS", 1600)),
            "energy": int(os.getenv("STAR_PACK_6_ENERGY", 4200)),
            "bonus_spins": 1,
            "description": "Festival bundle with radiant sticker showers and mega spins.",
            "art_url": "/static/images/star-pack-lumina.svg",
        },
        {
            "id": os.getenv("+7200 Energy", "energy_7200"),
            "name": "Orbital Riptide 7200",
            "stars": int(os.getenv("STAR_PACK_7_STARS", 2800)),
            "energy": int(os.getenv("STAR_PACK_7_ENERGY", 7200)),
            "bonus_spins": 1,
            "description": "Championship-grade hoard with cosmic wheel tokens for squads.",
            "art_url": "/static/images/star-pack-orbit.svg",
        },
    ]

    # Backwards compatibility for legacy single-pack logic
    PRODUCT_ENERGY_PACK_ID = STAR_PACKAGES[0]["id"]
    PRODUCT_ENERGY_PACK_AMOUNT_STARS = STAR_PACKAGES[0]["stars"]
    PRODUCT_ENERGY_PACK_ENERGY = STAR_PACKAGES[0]["energy"]
