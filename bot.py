import logging
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    LabeledPrice,
    ReplyKeyboardMarkup,
    Update,
    WebAppInfo,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    PreCheckoutQueryHandler,
    filters,
)
from sqlalchemy import select, create_engine
from sqlalchemy.orm import sessionmaker
from itsdangerous import URLSafeSerializer

from config import Config
from models import Base, Payment, RewardLink, User

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("sharkspin.bot")

engine = create_engine(Config.SQLALCHEMY_DATABASE_URI, future=True)
Session = sessionmaker(bind=engine, expire_on_commit=False, future=True)
Base.metadata.create_all(engine)

reward_signer = URLSafeSerializer(Config.SECRET_KEY, salt="sharkspin:reward")
ADMIN_ID = "1821897182"  # your Telegram user_id — replace with yours


def get_star_package(package_id: str | None):
    if not package_id:
        return None
    for pack in Config.STAR_PACKAGES:
        if pack["id"] == package_id:
            return pack
    return None


def build_star_keyboard():
    buttons = [
        [
            InlineKeyboardButton(
                f"{pack['name']} ({pack['stars']}⭐)",
                callback_data=f"buy:{pack['id']}",
            )
        ]
        for pack in Config.STAR_PACKAGES
    ]
    return InlineKeyboardMarkup(buttons)


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
    if start_args and start_args[0].startswith("buy_"):
        pack_id = start_args[0].split("buy_")[-1]
        pack = get_star_package(pack_id)
        if not pack:
            await update.message.reply_text("⚠️ That Star pack is no longer available.")
            return
        await send_star_invoice(update, context, pack)
        return

    text = (
        "🦈 Welcome to SharkSpin!\n\n"
        "Every spin, shop item, album, and leaderboard now lives inside the mini app interface.\n"
        "Launch it below whenever you need to manage rewards or explore updates.\n\n"
        "Commands:\n"
        "/play – open mini app\n"
        "/buy – Star shop menu\n"
        "/me – show your balance"
    )
    await update.message.reply_text(text, reply_markup=build_star_keyboard())


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
    pack_id = context.args[0] if context.args else None
    pack = get_star_package(pack_id) if pack_id else None
    if not pack:
        menu = "\n".join(
            [
                "• {name}: {energy}⚡ + {spins}🎡 for {stars}⭐ — {blurb} (use /buy {pid})".format(
                    name=p["name"],
                    energy=p["energy"],
                    spins=p["bonus_spins"],
                    stars=p["stars"],
                    blurb=p.get("description", ""),
                    pid=p["id"],
                )
                for p in Config.STAR_PACKAGES
            ]
        )
        await update.message.reply_text(
            "⭐ Star Shop Packs:\n" + menu,
            reply_markup=build_star_keyboard(),
        )
        return

    await send_star_invoice(update, context, pack)


async def send_star_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE, pack: dict):
    title = pack["name"]
    description = pack.get(
        "description",
        f"Buy {pack['energy']} energy and {pack['bonus_spins']} wheel tokens.",
    )
    payload = pack["id"]
    prices = [LabeledPrice(label=pack["name"], amount=pack["stars"])]

    await context.bot.send_invoice(
        chat_id=update.effective_chat.id,
        title=title,
        description=description,
        payload=payload,
        provider_token="",
        currency=CURRENCY,
        prices=prices,
    )


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data or ""
    if data.startswith("buy:"):
        pack_id = data.split(":", 1)[1]
        pack = get_star_package(pack_id)
        if not pack:
            await query.edit_message_text("⚠️ This Star pack is unavailable.")
            return
        await send_star_invoice(update, context, pack)


async def precheckout_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    await query.answer(ok=True)


async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sp = update.message.successful_payment
    stars_paid = sp.total_amount  # with Stars, amount is in stars (no fractional units)
    payload = sp.invoice_payload
    pack = get_star_package(payload)
    with Session() as s:
        u = s.execute(select(User).where(User.tg_user_id == str(update.effective_user.id))).scalar_one_or_none()
        if not u:
            return
        if not pack:
            pack = Config.STAR_PACKAGES[0]
        # Credit energy
        u.energy += pack["energy"]
        bonus_spins = pack.get("bonus_spins", 0)
        if bonus_spins:
            u.wheel_tokens += bonus_spins
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
        f"✅ Payment received: {stars_paid} ⭐️\nEnergy +{pack['energy']} & Wheel Tokens +{bonus_spins}. Enjoy spinning!"
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
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(PreCheckoutQueryHandler(precheckout_handler))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))
    app.run_polling(close_loop=False)

if __name__ == "__main__":
    main_polling()