import logging
from telegram import (
    Update,
    LabeledPrice,
    WebAppInfo,
    KeyboardButton,
    ReplyKeyboardMarkup
)
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    PreCheckoutQueryHandler,
    MessageHandler,
    filters,
)
from sqlalchemy import select, create_engine
from sqlalchemy.orm import sessionmaker
from itsdangerous import URLSafeSerializer

from config import Config
from models import User, Payment, Base, RewardLink

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("sharkspin.bot")

engine = create_engine(Config.SQLALCHEMY_DATABASE_URI, future=True)
Session = sessionmaker(bind=engine, expire_on_commit=False, future=True)
Base.metadata.create_all(engine)

CURRENCY = "XTR"  # IMPORTANT: Stars currency per Telegram docs

reward_signer = URLSafeSerializer(Config.SECRET_KEY, salt="sharkspin:reward")
ADMIN_ID = "1821897182"  # your Telegram user_id — replace with yours

async def reward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != ADMIN_ID:
        await update.message.reply_text("❌ You’re not authorized to create rewards.")
        return

    # Usage: /reward <type> <amount> <uses>
    if len(context.args) < 3:
        await update.message.reply_text("Usage: /reward <coins|energy|spins> <amount> <uses>")
        return

    rtype = context.args[0].lower()
    if rtype not in ["coins", "energy", "spins"]:
        await update.message.reply_text("❌ Invalid type. Use coins, energy, or spins.")
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

    # ✅ Use MarkdownV2 and escape special characters
    safe_url = url.replace("-", "\\-").replace("_", "\\_").replace(".", "\\.").replace("=", "\\=")
    msg = (
        f"🎁 *Reward Created!*\n"
        f"Type: `{rtype}`\n"
        f"Amount: `{amount}`\n"
        f"Uses: `{uses}`\n\n"
        f"[👉 Claim Here via Mini App]({safe_url})"
    )

    try:
        await update.message.reply_text(msg, parse_mode="MarkdownV2", disable_web_page_preview=True)
    except Exception as e:
        log.error(f"Error sending reward message: {e}")
        await update.message.reply_text(
            f"🎁 Reward created!\n\nType: {rtype}\nAmount: {amount}\nUses: {uses}\n\nLink:\n{url}"
        )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_user = update.effective_user
    with Session() as s:
        u = s.execute(select(User).where(User.tg_user_id == str(tg_user.id))).scalar_one_or_none()
        if not u:
            u = User(tg_user_id=str(tg_user.id), username=tg_user.username or tg_user.full_name,
                     coins=Config.STARTING_COINS, energy=Config.STARTING_ENERGY)
            s.add(u)
            s.commit()
    text = (
        "🦈 Welcome to SharkSpin!\n\n"
        "Spin to win coins. Buy energy with Telegram Stars.\n"
        "Open the mini app: Menu → Open (or tap /play).\n\n"
        "Commands:\n"
        "/play – open mini app\n"
        "/buy – purchase 100 energy (⭐ {stars} Stars)\n"
        "/me – show your balance".format(stars=Config.PRODUCT_ENERGY_PACK_AMOUNT_STARS)
    )
    await update.message.reply_text(text)


async def me(update: Update, context: ContextTypes.DEFAULT_TYPE):
    with Session() as s:
        u = s.execute(select(User).where(User.tg_user_id == str(update.effective_user.id))).scalar_one_or_none()
        if not u:
            await update.message.reply_text("Create an account with /start first.")
            return
        await update.message.reply_text(f"Coins: {u.coins}\nEnergy: {u.energy}")


async def play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = "https://game-tofumochi.pythonanywhere.com"
    kb = [[KeyboardButton("🎮 Open SharkSpin", web_app=WebAppInfo(url=url))]]
    await update.message.reply_text(
        "Tap below to open SharkSpin:",
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
    )


async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Send Stars invoice. No provider_token is needed for Stars.
    title = "Energy Pack"
    description = f"Buy {Config.PRODUCT_ENERGY_PACK_ENERGY} Energy for spins."
    payload = Config.PRODUCT_ENERGY_PACK_ID
    currency = CURRENCY
    prices = [LabeledPrice(label="Energy Pack", amount=Config.PRODUCT_ENERGY_PACK_AMOUNT_STARS)]  # amount in Stars

    await context.bot.send_invoice(
        chat_id=update.effective_chat.id,
        title=title,
        description=description,
        payload=payload,
        provider_token="",  # IMPORTANT for Stars
        currency=currency,
        prices=prices,
    )


async def precheckout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    await query.answer(ok=True)


async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sp = update.message.successful_payment
    stars_paid = sp.total_amount  # with Stars, amount is in stars (no fractional units)
    payload = sp.invoice_payload
    with Session() as s:
        u = s.execute(select(User).where(User.tg_user_id == str(update.effective_user.id))).scalar_one_or_none()
        if not u:
            return
        # Credit energy
        u.energy += Config.PRODUCT_ENERGY_PACK_ENERGY
        # Record payment
        p = Payment(
            tg_payment_charge_id=sp.telegram_payment_charge_id,
            payload=payload,
            stars_amount=stars_paid,
            user_id=u.id,
        )
        s.add(p)
        s.commit()
    await update.message.reply_text(
        f"✅ Payment received: {stars_paid} ⭐️\nEnergy +{Config.PRODUCT_ENERGY_PACK_ENERGY}. Enjoy spinning!"
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
    app.add_handler(CommandHandler("play", play))
    app.add_handler(CommandHandler("buy", buy))
    app.add_handler(PreCheckoutQueryHandler(precheckout_handler))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))
    app.run_polling(close_loop=False)

if __name__ == "__main__":
    main_polling()