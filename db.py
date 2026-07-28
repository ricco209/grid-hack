# -*- coding: utf-8 -*-
"""
GRID // HACK — общий слой данных (SQLite)
Используется и app.py (веб-часть), и bot.py (бот), поэтому весь баланс,
рефералы, чек-ины и задания всегда синхронизированы между ними.

Совместимо с Python 3.8.10 — только стандартная библиотека, без внешних
зависимостей для работы с БД.
"""

import os
import sqlite3
import secrets
import string
import threading
import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "grid_hack.db"))

_lock = threading.Lock()

# ---------- Экономика игры (легко настраивается в одном месте) ----------
CHECKIN_REWARD = 100_000        # "Daily Check-in" / кнопка "Collect Your Daily Shells"
BONUS_REWARD = 20_000           # доп. карточка "Daily Shell Bonus"
JOIN_CHANNEL_REWARD = 50_000    # задание "Join the Channel"
INVITE_REWARD = 200_000         # бонус за первого приглашённого друга
CHEST_REWARD = 50_000           # сундук за выполнение всех заданий за день
STREAK_STEP = 10_000            # + за каждый день стрика (до кап-а)
STREAK_CAP_DAYS = 7             # максимум дней, которые считаются в бонус стрика

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    balance INTEGER NOT NULL DEFAULT 0,
    streak INTEGER NOT NULL DEFAULT 0,
    last_checkin TEXT,
    last_bonus TEXT,
    referral_code TEXT UNIQUE,
    referred_by INTEGER,
    joined_channel INTEGER NOT NULL DEFAULT 0,
    invite_bonus_given INTEGER NOT NULL DEFAULT 0,
    chest_claimed_date TEXT,
    island INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_users_balance ON users(balance DESC);
CREATE INDEX IF NOT EXISTS idx_users_referred_by ON users(referred_by);
CREATE INDEX IF NOT EXISTS idx_users_island ON users(island);
"""


def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db():
    with _lock:
        conn = get_conn()
        try:
            conn.executescript(SCHEMA)
            conn.commit()
        finally:
            conn.close()


def _today():
    return datetime.date.today().isoformat()


def _gen_ref_code(conn):
    alphabet = string.ascii_uppercase + string.digits
    while True:
        code = "".join(secrets.choice(alphabet) for _ in range(7))
        if not conn.execute(
            "SELECT 1 FROM users WHERE referral_code=?", (code,)
        ).fetchone():
            return code


def _row_to_dict(row):
    return dict(row) if row is not None else None


def get_user(user_id):
    conn = get_conn()
    try:
        return _row_to_dict(conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone())
    finally:
        conn.close()


def get_user_by_ref_code(code):
    conn = get_conn()
    try:
        return _row_to_dict(
            conn.execute("SELECT * FROM users WHERE referral_code=?", (code,)).fetchone()
        )
    finally:
        conn.close()


def get_or_create_user(user_id, username=None, first_name=None, referred_by=None):
    """Idempotent: safe to call on every WebApp load / every /start."""
    with _lock:
        conn = get_conn()
        try:
            row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
            if row:
                # держим username/first_name свежими, но не трогаем баланс и т.д.
                conn.execute(
                    "UPDATE users SET username=?, first_name=? WHERE id=?",
                    (username, first_name, user_id),
                )
                conn.commit()
                return _row_to_dict(conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone())

            # реферер не может сам себя пригласить
            if referred_by == user_id:
                referred_by = None
            # реферер должен существовать
            if referred_by is not None:
                ref_row = conn.execute("SELECT id FROM users WHERE id=?", (referred_by,)).fetchone()
                if not ref_row:
                    referred_by = None

            code = _gen_ref_code(conn)
            island = user_id % 5  # 5 "островов" — лёгкое шардирование для отдельного лидерборда
            now = datetime.datetime.utcnow().isoformat()
            conn.execute(
                """INSERT INTO users
                   (id, username, first_name, referral_code, referred_by, island, created_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (user_id, username, first_name, code, referred_by, island, now),
            )
            conn.commit()

            # первый реферал друга сразу приносит рефереру бонус (задание "Invite Mates")
            if referred_by is not None:
                ref_row = conn.execute("SELECT * FROM users WHERE id=?", (referred_by,)).fetchone()
                if ref_row and not ref_row["invite_bonus_given"]:
                    conn.execute(
                        "UPDATE users SET balance = balance + ?, invite_bonus_given = 1 WHERE id=?",
                        (INVITE_REWARD, referred_by),
                    )
                    conn.commit()

            return _row_to_dict(conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone())
        finally:
            conn.close()


def set_referral(user_id, code):
    """Ручной ввод реферального кода — для тех, кто открыл приложение не по ссылке."""
    with _lock:
        conn = get_conn()
        try:
            row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
            if not row:
                return {"ok": False, "error": "user_not_found"}
            if row["referred_by"] is not None:
                return {"ok": False, "error": "already_set"}
            code = (code or "").strip().upper()
            ref = conn.execute("SELECT * FROM users WHERE referral_code=?", (code,)).fetchone()
            if not ref or ref["id"] == user_id:
                return {"ok": False, "error": "invalid_code"}
            conn.execute("UPDATE users SET referred_by=? WHERE id=?", (ref["id"], user_id))
            if not ref["invite_bonus_given"]:
                conn.execute(
                    "UPDATE users SET balance = balance + ?, invite_bonus_given = 1 WHERE id=?",
                    (INVITE_REWARD, ref["id"]),
                )
            conn.commit()
            return {"ok": True, "referrer_name": ref["first_name"] or ref["username"] or "Player"}
        finally:
            conn.close()


def do_checkin(user_id):
    """Ежедневный сбор ракушек. Возвращает dict с результатом."""
    with _lock:
        conn = get_conn()
        try:
            row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
            if not row:
                return {"ok": False, "error": "user_not_found"}
            today = _today()
            if row["last_checkin"] == today:
                return {"ok": False, "error": "already_claimed", "streak": row["streak"]}

            yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
            streak = row["streak"] + 1 if row["last_checkin"] == yesterday else 1
            capped = min(streak, STREAK_CAP_DAYS)
            reward = CHECKIN_REWARD + (capped - 1) * STREAK_STEP

            conn.execute(
                "UPDATE users SET balance = balance + ?, streak = ?, last_checkin = ? WHERE id=?",
                (reward, streak, today, user_id),
            )
            conn.commit()
            new_balance = conn.execute("SELECT balance FROM users WHERE id=?", (user_id,)).fetchone()["balance"]
            return {"ok": True, "reward": reward, "streak": streak, "balance": new_balance}
        finally:
            conn.close()


def claim_bonus(user_id):
    with _lock:
        conn = get_conn()
        try:
            row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
            if not row:
                return {"ok": False, "error": "user_not_found"}
            today = _today()
            if row["last_bonus"] == today:
                return {"ok": False, "error": "already_claimed"}
            conn.execute(
                "UPDATE users SET balance = balance + ?, last_bonus = ? WHERE id=?",
                (BONUS_REWARD, today, user_id),
            )
            conn.commit()
            new_balance = conn.execute("SELECT balance FROM users WHERE id=?", (user_id,)).fetchone()["balance"]
            return {"ok": True, "reward": BONUS_REWARD, "balance": new_balance}
        finally:
            conn.close()


def verify_join_channel(user_id, is_member):
    with _lock:
        conn = get_conn()
        try:
            row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
            if not row:
                return {"ok": False, "error": "user_not_found"}
            if row["joined_channel"]:
                return {"ok": True, "already": True, "balance": row["balance"]}
            if not is_member:
                return {"ok": False, "error": "not_member"}
            conn.execute(
                "UPDATE users SET balance = balance + ?, joined_channel = 1 WHERE id=?",
                (JOIN_CHANNEL_REWARD, user_id),
            )
            conn.commit()
            new_balance = conn.execute("SELECT balance FROM users WHERE id=?", (user_id,)).fetchone()["balance"]
            return {"ok": True, "reward": JOIN_CHANNEL_REWARD, "balance": new_balance}
        finally:
            conn.close()


def claim_chest(user_id):
    """Сундук: доступен только когда все 3 задания на сегодня выполнены."""
    with _lock:
        conn = get_conn()
        try:
            row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
            if not row:
                return {"ok": False, "error": "user_not_found"}
            today = _today()
            if row["chest_claimed_date"] == today:
                return {"ok": False, "error": "already_claimed"}
            has_referral = conn.execute(
                "SELECT 1 FROM users WHERE referred_by=?", (user_id,)
            ).fetchone() is not None
            eligible = bool(row["joined_channel"]) and row["last_checkin"] == today and has_referral
            if not eligible:
                return {"ok": False, "error": "not_eligible"}
            conn.execute(
                "UPDATE users SET balance = balance + ?, chest_claimed_date = ? WHERE id=?",
                (CHEST_REWARD, today, user_id),
            )
            conn.commit()
            new_balance = conn.execute("SELECT balance FROM users WHERE id=?", (user_id,)).fetchone()["balance"]
            return {"ok": True, "reward": CHEST_REWARD, "balance": new_balance}
        finally:
            conn.close()


def rank_of(user_id, scope="global"):
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        if not row:
            return None
        if scope == "island":
            higher = conn.execute(
                "SELECT COUNT(*) c FROM users WHERE island=? AND balance > ?",
                (row["island"], row["balance"]),
            ).fetchone()["c"]
        else:
            higher = conn.execute(
                "SELECT COUNT(*) c FROM users WHERE balance > ?", (row["balance"],)
            ).fetchone()["c"]
        return higher + 1
    finally:
        conn.close()


def leaderboard(scope, user_id, limit=5):
    conn = get_conn()
    try:
        me = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        if scope == "friends":
            rows = conn.execute(
                """SELECT * FROM users
                   WHERE id = ? OR referred_by = ? OR id = (SELECT referred_by FROM users WHERE id=?)
                   ORDER BY balance DESC LIMIT ?""",
                (user_id, user_id, user_id, limit),
            ).fetchall()
        elif scope == "island" and me:
            rows = conn.execute(
                "SELECT * FROM users WHERE island=? ORDER BY balance DESC LIMIT ?",
                (me["island"], limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM users ORDER BY balance DESC LIMIT ?", (limit,)
            ).fetchall()

        top = [dict(r) for r in rows]
        top_ids = {r["id"] for r in top}
        me_entry = None
        if me and me["id"] not in top_ids:
            me_entry = dict(me)
            me_entry["rank"] = rank_of(user_id, scope if scope in ("island",) else "global")
        for i, r in enumerate(top, start=1):
            r["rank"] = i
        return {"top": top, "me": me_entry}
    finally:
        conn.close()


def friends_of(user_id):
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM users WHERE referred_by=? ORDER BY balance DESC", (user_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()