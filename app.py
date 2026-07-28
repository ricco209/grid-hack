# -*- coding: utf-8 -*-
"""
GRID // HACK — Flask backend
Совместимо с Python 3.8.10 (Flask 2.0.x, никакого async / Node.js не нужно)

Отдаёт Telegram Mini App (static/index.html) и JSON API: баланс, ежедневный
чек-ин, задания, рефералы, лидерборд. Хранилище — SQLite (db.py), общее
с bot.py.
"""

import os
import hmac
import json
import hashlib
import logging
from urllib.parse import parse_qsl

import urllib.request
import urllib.error

from flask import Flask, jsonify, request, send_from_directory

import db

APP_DIR = os.path.dirname(os.path.abspath(__file__))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("grid-hack")

app = Flask(__name__, static_folder="static")

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "")  # напр. @your_channel — для проверки подписки
DEBUG_MODE = os.environ.get("FLASK_DEBUG", "1") == "1"
DEMO_USER_ID = 1000000001  # используется только вне Telegram (локальный просмотр в браузере)

db.init_db()

FACTS = [
    "Первый компьютерный «баг» был в буквальном смысле мотыльком, застрявшим в реле.",
    "Пароль «123456» до сих пор входит в топ самых популярных в мире.",
    "Клавиатура QWERTY была придумана, чтобы печатные машинки не заедали.",
    "Первый домен в интернете был зарегистрирован в 1985 году.",
    "Слово «robot» происходит от чешского слова «robota» — подневольный труд.",
    "Первое письмо, отправленное по электронной почте, ушло в 1971 году.",
    "В 1969 году интернет состоял всего из четырёх подключённых компьютеров.",
    "Значок «@» использовался в бухгалтерии ещё до появления электронной почты.",
    "Смайлик ':-)' придумали в 1982 году как способ показать шутку в тексте.",
    "Первая веб-камера следила за кофеваркой в Кембриджском университете.",
]

import random  # noqa: E402  (после FACTS ради читаемости, влияния на работу нет)


# ---------- Telegram initData проверка ----------

def validate_init_data(init_data):
    """Проверяет подпись initData от Telegram WebApp. Возвращает dict полей или None."""
    if not init_data or not BOT_TOKEN:
        return None
    try:
        pairs = dict(parse_qsl(init_data, strict_parsing=True))
    except ValueError:
        return None
    received_hash = pairs.pop("hash", None)
    if not received_hash:
        return None
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calculated_hash, received_hash):
        return None
    return pairs


def current_user():
    """Достаёт (и при необходимости создаёт) пользователя из initData текущего запроса."""
    init_data = request.headers.get("X-Init-Data", "")
    pairs = validate_init_data(init_data)

    if pairs is None:
        if not DEBUG_MODE:
            return None
        # Локальный просмотр вне Telegram — демо-пользователь, чтобы UI можно было тестировать.
        user_id, username, first_name = DEMO_USER_ID, "demo", "Demo"
        referred_by = None
    else:
        try:
            tg_user = json.loads(pairs.get("user", "{}"))
        except (TypeError, ValueError):
            tg_user = {}
        user_id = tg_user.get("id")
        if user_id is None:
            return None
        username = tg_user.get("username")
        first_name = tg_user.get("first_name", "Player")
        referred_by = None
        start_param = pairs.get("start_param", "")
        if start_param.startswith("ref_"):
            ref_user = db.get_user_by_ref_code(start_param[4:])
            if ref_user:
                referred_by = ref_user["id"]

    return db.get_or_create_user(user_id, username, first_name, referred_by=referred_by)


def check_channel_membership(user_id):
    """Спрашивает у Telegram Bot API, состоит ли пользователь в канале CHANNEL_ID."""
    if not BOT_TOKEN or not CHANNEL_ID:
        # Верификация не настроена — засчитываем по нажатию (честная система появится,
        # как только заданы BOT_TOKEN и CHANNEL_ID).
        return True
    url = (
        f"https://api.telegram.org/bot{BOT_TOKEN}/getChatMember"
        f"?chat_id={CHANNEL_ID}&user_id={user_id}"
    )
    try:
        with urllib.request.urlopen(url, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError):
        log.warning("getChatMember: сеть/ответ Telegram недоступны, отклоняю задание")
        return False
    if not data.get("ok"):
        return False
    status = data["result"].get("status")
    return status in ("member", "administrator", "creator")


def user_public(u):
    """Преобразует строку БД в то, что видит фронтенд (без служебных полей)."""
    return {
        "id": u["id"],
        "username": u["username"],
        "first_name": u["first_name"],
        "balance": u["balance"],
        "streak": u["streak"],
        "checked_in_today": u["last_checkin"] == db._today(),
        "bonus_claimed_today": u["last_bonus"] == db._today(),
        "joined_channel": bool(u["joined_channel"]),
        "chest_claimed_today": u["chest_claimed_date"] == db._today(),
        "referral_code": u["referral_code"],
        "referred": u["referred_by"] is not None,
    }


# ---------- Статика / Mini App ----------

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(app.static_folder, filename)


# ---------- API ----------

@app.route("/api/me")
def api_me():
    u = current_user()
    if not u:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    has_referral = len(db.friends_of(u["id"])) > 0
    payload = user_public(u)
    payload["rank"] = db.rank_of(u["id"])
    payload["has_referral"] = has_referral
    payload["chest_eligible"] = (
        payload["joined_channel"] and payload["checked_in_today"] and has_referral
        and not payload["chest_claimed_today"]
    )
    return jsonify({"ok": True, "user": payload})


@app.route("/api/checkin", methods=["POST"])
def api_checkin():
    u = current_user()
    if not u:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    result = db.do_checkin(u["id"])
    return jsonify(result)


@app.route("/api/bonus/claim", methods=["POST"])
def api_bonus_claim():
    u = current_user()
    if not u:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    result = db.claim_bonus(u["id"])
    return jsonify(result)


@app.route("/api/tasks/join_channel/verify", methods=["POST"])
def api_join_channel_verify():
    u = current_user()
    if not u:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    is_member = check_channel_membership(u["id"])
    result = db.verify_join_channel(u["id"], is_member)
    return jsonify(result)


@app.route("/api/tasks/chest/claim", methods=["POST"])
def api_chest_claim():
    u = current_user()
    if not u:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    result = db.claim_chest(u["id"])
    return jsonify(result)


@app.route("/api/leaderboard")
def api_leaderboard():
    u = current_user()
    if not u:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    scope = request.args.get("scope", "global")
    if scope not in ("global", "friends", "island"):
        scope = "global"
    data = db.leaderboard(scope, u["id"], limit=5)

    def fmt(row, rank):
        return {
            "rank": rank,
            "id": row["id"],
            "name": row["first_name"] or row["username"] or "Player",
            "balance": row["balance"],
            "is_me": row["id"] == u["id"],
        }

    top = [fmt(r, r["rank"]) for r in data["top"]]
    me = fmt(data["me"], data["me"]["rank"]) if data["me"] else None
    return jsonify({"ok": True, "scope": scope, "top": top, "me": me})


@app.route("/api/referral/apply", methods=["POST"])
def api_referral_apply():
    u = current_user()
    if not u:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    body = request.get_json(silent=True) or {}
    result = db.set_referral(u["id"], body.get("code", ""))
    return jsonify(result)


@app.route("/api/friends")
def api_friends():
    u = current_user()
    if not u:
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    friends = db.friends_of(u["id"])
    bot_username = os.environ.get("BOT_USERNAME", "")
    # /start (не startapp) — надёжно ловится обработчиком bot.py в любом боте,
    # без зависимости от настройки Direct Link Mini App в BotFather.
    link = f"https://t.me/{bot_username}?start=ref_{u['referral_code']}" if bot_username else ""
    return jsonify({
        "ok": True,
        "referral_code": u["referral_code"],
        "invite_link": link,
        "friends": [
            {"name": f["first_name"] or f["username"] or "Player", "balance": f["balance"]}
            for f in friends
        ],
        "invite_reward": db.INVITE_REWARD,
    })


@app.route("/api/fact")
def random_fact():
    return jsonify({"ok": True, "fact": random.choice(FACTS)})


@app.route("/healthz")
def healthz():
    return jsonify({"ok": True})


if __name__ == "__main__":
    # Только для локальной разработки. На Render/сервере gunicorn запускает `app:app`.
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=DEBUG_MODE)