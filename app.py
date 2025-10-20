from flask import Flask, jsonify, request, render_template, abort
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from itsdangerous import URLSafeSerializer, BadSignature

from config import Config
from models import Base, User, Spin, RewardLink
from game_logic import apply_spin

app = Flask(__name__)
app.config.from_object(Config)

engine = create_engine(Config.SQLALCHEMY_DATABASE_URI, future=True)
Session = sessionmaker(bind=engine, expire_on_commit=False, future=True)
Base.metadata.create_all(engine)

# Sign mini app init data (optional – extra layer beyond Telegram WebApp initData)
signer = URLSafeSerializer(Config.SECRET_KEY, salt="sharkspin:webapp")
reward_signer = URLSafeSerializer(Config.SECRET_KEY, salt="sharkspin:reward")

@app.get("/")
def index():
    return render_template("index.html")

def generate_reward_link(amount=100, type_="coins"):
    payload = {"type": type_, "amount": amount}
    token = reward_signer.dumps(payload)
    return f"https://game-tofumochi.pythonanywhere.com/redeem/{token}"

@app.get("/redeem/<token>")
def redeem_reward(token):
    # 1️⃣ Validate token signature
    try:
        reward = reward_signer.loads(token)
    except Exception:
        return render_template("redeem.html", message="❌ Invalid or expired reward link.")

    tg_user_id = request.args.get("tg_user_id")

    # 2️⃣ Make sure it's coming from inside Telegram
    if not tg_user_id or tg_user_id == "{tg_user_id}":
        return render_template(
            "redeem.html",
            message="⚠️ You must open this link inside SharkSpin (Telegram Mini App)."
        )

    # 3️⃣ Load reward + user from DB
    with Session() as s:
        rl = s.execute(select(RewardLink).where(RewardLink.token == token)).scalar_one_or_none()
        if not rl or not rl.is_active or rl.uses_left <= 0:
            return render_template("redeem.html", message="🚫 This reward link has expired or was already used.")

        user = s.execute(select(User).where(User.tg_user_id == str(tg_user_id))).scalar_one_or_none()
        if not user:
            return render_template("redeem.html", message="❌ You don’t have a SharkSpin account yet! Use /start first.")

        # 4️⃣ Apply the reward based on type
        if rl.reward_type == "coins":
            user.coins += rl.amount
        elif rl.reward_type == "energy":
            user.energy += rl.amount
        elif rl.reward_type == "spins":
            user.energy += rl.amount * 5  # example conversion
        else:
            return render_template("redeem.html", message="❌ Invalid reward type.")

        # 5️⃣ Decrease uses left
        rl.uses_left -= 1
        if rl.uses_left <= 0:
            rl.is_active = False

        s.commit()

        msg = f"🎁 You received {rl.amount} {rl.reward_type.capitalize()}! ({rl.uses_left} uses left)"
        return render_template("redeem.html", message=msg)




@app.post("/api/auth")
def api_auth():
    # Client sends Telegram WebApp initData for validation. For MVP, accept tg_user_id.
    data = request.get_json(force=True)
    tg_user_id = str(data.get("tg_user_id"))
    username = data.get("username")
    if not tg_user_id:
        abort(400)
    with Session() as s:
        user = s.execute(select(User).where(User.tg_user_id == tg_user_id)).scalar_one_or_none()
        if not user:
            user = User(
                tg_user_id=tg_user_id,
                username=username,
                coins=Config.STARTING_COINS,
                energy=Config.STARTING_ENERGY,
            )
            s.add(user)
            s.commit()
        token = signer.dumps({"u": tg_user_id})
        return jsonify({
            "ok": True,
            "token": token,
            "coins": user.coins,
            "energy": user.energy,
        })


def _get_user_from_token(token):
    try:
        payload = signer.loads(token)
        tg_user_id = payload.get("u")
    except BadSignature:
        return None
    with Session() as s:
        return s.execute(select(User).where(User.tg_user_id == str(tg_user_id))).scalar_one_or_none()

@app.post("/api/spin")
def api_spin():
    payload = request.get_json(force=True)
    token = payload.get("token")
    user = _get_user_from_token(token)
    if not user:
        abort(401)
    with Session() as s:
        # refresh user from this session
        user = s.merge(user)
        ok, msg, payout, result_name = apply_spin(user)
        if not ok:
            return jsonify({"ok": False, "error": msg}), 200
        rec = Spin(user_id=user.id, delta_coins=payout, result=result_name)
        s.add(rec)
        s.commit()
        return jsonify({
            "ok": True,
            "payout": payout,
            "result": result_name,
            "coins": user.coins,
            "energy": user.energy,
        })

@app.get("/api/me")
def api_me():
    token = request.args.get("token")
    user = _get_user_from_token(token)
    if not user:
        abort(401)
    return jsonify({"ok": True, "coins": user.coins, "energy": user.energy})
