import os

class Config:
    # Flask
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    SQLALCHEMY_DATABASE_URI = os.getenv(
    "DATABASE_URL", "sqlite:////home/tofumochi/sharkspin/sharkspin.db")
    SQLALCHEMY_ECHO = False

    # Telegram
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8220458714:AAHJeibywqHXQf1bJp0bQbvjpEO0gaLhQOM")
    # TELEGRAM_WEBHOOK_URL = os.getenv("TELEGRAM_WEBHOOK_URL", "https://game-tofumochi.pythonanywhere.com/bot/webhook")  # https://game-tofumochi.pythonanywhere.com/bot/webhook

    # Game
    STARTING_COINS = int(os.getenv("STARTING_COINS", 100))
    STARTING_ENERGY = int(os.getenv("STARTING_ENERGY", 25))
    ENERGY_PER_SPIN = int(os.getenv("ENERGY_PER_SPIN", 1))
    SPIN_COOLDOWN_MS = int(os.getenv("SPIN_COOLDOWN_MS", 1200))

    # Wheel of fortune
    DAILY_FREE_WHEEL_SPINS = int(os.getenv("DAILY_FREE_WHEEL_SPINS", 1))
    WHEEL_COOLDOWN_HOURS = int(os.getenv("WHEEL_COOLDOWN_HOURS", 4))
    WHEEL_TOKEN_COST = int(os.getenv("WHEEL_TOKEN_COST", 1))

    # Payments (Stars / XTR)
    # Using Stars: currency must be "XTR" per Telegram docs.
    PRODUCT_ENERGY_PACK_ID = os.getenv("PRODUCT_ENERGY_PACK_ID", "energy_100")
    PRODUCT_ENERGY_PACK_AMOUNT_STARS = int(os.getenv("PRODUCT_ENERGY_PACK_AMOUNT_STARS", 50))  # 50 Stars
    PRODUCT_ENERGY_PACK_ENERGY = int(os.getenv("PRODUCT_ENERGY_PACK_ENERGY", 100))