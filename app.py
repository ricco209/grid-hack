"""
Matrix Grid Hack — Flask backend
Compatible with Python 3.8.10 (Flask 2.0.x, no async / no Node.js needed)

Serves the Telegram Mini App (static/index.html) and a tiny JSON API
for saving/reading best scores. Scores are stored in a local SQLite
file so there are no extra services to run.
"""

import os
import sqlite3
import time
from flask import Flask, jsonify, request, send_from_directory

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(APP_DIR, "scores.db")

app = Flask(__name__, static_folder="static", template_folder="templates")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS scores (
            user_id TEXT PRIMARY KEY,
            username TEXT,
            best_score INTEGER NOT NULL DEFAULT 0,
            updated_at INTEGER NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


# ---------- Static / Mini App ----------

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(app.static_folder, filename)


# ---------- API ----------

@app.route("/api/score", methods=["POST"])
def submit_score():
    data = request.get_json(silent=True) or {}
    user_id = str(data.get("user_id", "")).strip()
    username = str(data.get("username", "anonymous"))[:64]
    score = int(data.get("score", 0))

    if not user_id:
        return jsonify({"ok": False, "error": "missing user_id"}), 400
    if score < 0 or score > 1_000_000:
        return jsonify({"ok": False, "error": "invalid score"}), 400

    conn = get_db()
    row = conn.execute(
        "SELECT best_score FROM scores WHERE user_id = ?", (user_id,)
    ).fetchone()

    if row is None:
        conn.execute(
            "INSERT INTO scores (user_id, username, best_score, updated_at) VALUES (?, ?, ?, ?)",
            (user_id, username, score, int(time.time())),
        )
        best = score
    else:
        best = max(row["best_score"], score)
        conn.execute(
            "UPDATE scores SET username = ?, best_score = ?, updated_at = ? WHERE user_id = ?",
            (username, best, int(time.time()), user_id),
        )

    conn.commit()
    conn.close()
    return jsonify({"ok": True, "best_score": best})


@app.route("/api/leaderboard", methods=["GET"])
def leaderboard():
    conn = get_db()
    rows = conn.execute(
        "SELECT username, best_score FROM scores ORDER BY best_score DESC LIMIT 10"
    ).fetchall()
    conn.close()
    return jsonify({"ok": True, "leaderboard": [dict(r) for r in rows]})


@app.route("/healthz")
def healthz():
    return jsonify({"ok": True})


init_db()

if __name__ == "__main__":
    # Local dev only. On Render, gunicorn runs `app:app` (see Procfile).
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
