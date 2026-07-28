"""
GRID // HACK — Flask backend
Compatible with Python 3.8.10 (Flask 2.0.x, no async / no Node.js needed)

Serves the Telegram Mini App (static/index.html) and a tiny JSON API
that returns a random fact. No game, no score tracking, no database.
"""

import os
import random
from flask import Flask, jsonify, send_from_directory

APP_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, static_folder="static", template_folder="templates")

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


# ---------- Static / Mini App ----------

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(app.static_folder, filename)


# ---------- API ----------

@app.route("/api/fact", methods=["GET"])
def random_fact():
    return jsonify({"ok": True, "fact": random.choice(FACTS)})


@app.route("/healthz")
def healthz():
    return jsonify({"ok": True})


if __name__ == "__main__":
    # Local dev only. On Render, gunicorn runs `app:app` (see Procfile).
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)