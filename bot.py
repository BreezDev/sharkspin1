import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes
from sqlalchemy import select, create_engine
from sqlalchemy.orm import sessionmaker
from itsdangerous import URLSafeSerializer

from config import Config
from models import Base, RewardLink, User

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("sharkspin.bot")

engine = create_engine(Config.SQLALCHEMY_DATABASE_URI, future=True)
Session = sessionmaker(bind=engine, expire_on_commit=False, future=True)
Base.metadata.create_all(engine)

reward_signer = URLSafeSerializer(Config.SECRET_KEY, salt="sharkspin:reward")
ADMIN_ID = "1821897182"  # your Telegram user_id — replace with yours

def build_webapp_markup(label: str = "Open SharkSpin", path: str | None = None):
    url = Config.WEBAPP_URL.rstrip("/")
    if path:
        url = f"{url}/{path.lstrip('/')}"
    button = InlineKeyboardButton(label, web_app=WebAppInfo(url=url))
    return InlineKeyboardMarkup([[button]])


async def reward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != ADMIN_ID:
        await update.message.reply_text("❌ You’re not authorized to create rewards.")
        return

    # Usage: /reward <type> <amount> <uses>
    if len(context.args) < 3:
        await update.message.reply_text(
            "Usage: /reward <coins|energy|spins|wheel_tokens|sticker_pack> <amount> <uses>"
        )
        return

    rtype = context.args[0].lower()
    if rtype not in ["coins", "energy", "spins", "wheel_tokens", "sticker_pack"]:
        await update.message.reply_text(
            "❌ Invalid type. Use coins, energy, spins, wheel_tokens, or sticker_pack."
        )
        return

    try:
        amount = int(context.args[1])
        uses = int(context.args[2])
    except ValueError:
        await update.message.reply_text("⚠️ Amount and uses must be numbers.")
        return

    # create signed token
    payload = {"type": rtype, "amount": amount}
    token = reward_signer.dumps(payload)

    # save in DB
    with Session() as s:
        existing = (
            s.execute(select(RewardLink).where(RewardLink.token == token)).scalar_one_or_none()
        )
        if existing:
            rl = existing
            rl.reward_type = rtype
            rl.amount = amount
            rl.uses_left = uses
            rl.is_active = True
            rl.created_by = str(update.effective_user.id)
        else:
            rl = RewardLink(
                token=token,
                reward_type=rtype,
                amount=amount,
                uses_left=uses,
                created_by=str(update.effective_user.id),
            )
            s.add(rl)
        s.commit()

    bot_username = (await context.bot.get_me()).username
    url = f"https://t.me/{bot_username}/startapp?startapp=redeem_{token}"

    markup = InlineKeyboardMarkup(
        [[InlineKeyboardButton("🎁 Open reward in SharkSpin", url=url)]]
    )

    summary = (
        "🎁 Reward Created!\n"
        f"Type: {rtype}\n"
        f"Amount: {amount}\n"
        f"Uses: {uses}\n\n"
        "Tap the button below to launch the mini app and auto-apply the grant."
    )

    await update.message.reply_text(summary, reply_markup=markup, disable_web_page_preview=True)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_user = update.effective_user
    start_args = context.args
    with Session() as s:
        u = s.execute(select(User).where(User.tg_user_id == str(tg_user.id))).scalar_one_or_none()
        if not u:
            u = User(tg_user_id=str(tg_user.id), username=tg_user.username or tg_user.full_name,
                     coins=Config.STARTING_COINS, energy=Config.STARTING_ENERGY)
            s.add(u)
            s.commit()
    text = (
        "🦈 Welcome to SharkSpin!\n\n"
        "Every spin, shop item, album, and leaderboard now lives inside the mini app interface.\n"
        "Launch it below whenever you need to manage rewards or explore updates.\n\n"
        "Commands:\n"
        "/buy – Star shop menu\n"
        "/me – show your balance"
    )
    await update.message.reply_text(text, reply_markup=build_webapp_markup())


async def me(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with Session() as s:
        u = s.execute(select(User).where(User.tg_user_id == str(update.effective_user.id))).scalar_one_or_none()
        if not u:
            await update.message.reply_text("Create an account with /start first.")
            return
        await update.message.reply_text(
            f"Coins: {u.coins}\nEnergy: {u.energy}",
            reply_markup=build_webapp_markup("Open SharkSpin"),
        )


async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    menu = "\n".join(
        [
            "• {name}: {energy}⚡ + {spins}🌀 for {stars}⭐".format(
                name=p["name"],
                energy=p["energy"],
                spins=p["bonus_spins"],
                stars=p["stars"],
            )
            for p in Config.STAR_PACKAGES
        ]
    )
    text = (
        "⭐ The Star Market now lives directly inside the SharkSpin mini app.\n"
        "Browse packs, review art, and confirm purchases without leaving the experience.\n\n"
        "Featured bundles:\n"
        f"{menu}"
    )
    await update.message.reply_text(
        text,
        reply_markup=build_webapp_markup("Open Star Market", "#shopSection"),
        disable_web_page_preview=True,
    )


def build_app():
    return Application.builder().token(Config.TELEGRAM_BOT_TOKEN).build()


async def on_webhook(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return  # placeholder if you route via Flask; otherwise run bot separately.


def main_polling():
    app = build_app()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reward", reward))
    app.add_handler(CommandHandler("me", me))
    app.add_handler(CommandHandler("buy", buy))
    app.run_polling(close_loop=False)

if __name__ == "__main__":
    main_polling()