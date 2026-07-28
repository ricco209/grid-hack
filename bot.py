# -*- coding: utf-8 -*-
"""
GRID // HACK — Telegram bot launcher
python-telegram-bot 13.x (синхронный API) — работает на Python 3.7+,
включая 3.8.10, без asyncio и без Node.js.

Перед запуском задайте переменные окружения:
  BOT_TOKEN     - токен от @BotFather (НИКОГДА не храните его в коде!)
  WEBAPP_URL    - адрес вашего задеплоенного приложения,
                  например https://your-app.onrender.com
  BOT_USERNAME  - username бота без @ (нужен для реферальных ссылок)
  CHANNEL_ID    - (опц.) @username канала для проверки подписки в задании
"""

import os
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo, Update
from telegram.ext import Updater, CommandHandler, CallbackContext

import db

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
log = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
WEBAPP_URL = os.environ.get("WEBAPP_URL", "https://your-app.onrender.com")

db.init_db()


def start(update: Update, context: CallbackContext):
    tg_user = update.effective_user

    # Реферальная ссылка вида /start ref_ABC1234 — фиксируем, кто кого пригласил.
    referred_by = None
    if context.args:
        arg = context.args[0]
        if arg.startswith("ref_"):
            ref_user = db.get_user_by_ref_code(arg[4:])
            if ref_user:
                referred_by = ref_user["id"]

    db.get_or_create_user(
        tg_user.id, tg_user.username, tg_user.first_name, referred_by=referred_by
    )

    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("🥥 Открыть GRID // HACK", web_app=WebAppInfo(url=WEBAPP_URL))]]
    )
    update.message.reply_text(
        "GRID // HACK\n\n"
        "Собирай ракушки, выполняй задания и поднимайся в топе исследователей пляжа.\n"
        "Открывай приложение, чтобы забрать свои SAND!",
        reply_markup=keyboard,
    )


def help_cmd(update: Update, context: CallbackContext):
    update.message.reply_text("/start — открыть игру\n/help — это сообщение")


def main():
    if not BOT_TOKEN:
        raise SystemExit(
            "Переменная окружения BOT_TOKEN не задана. "
            "Установите её перед запуском (см. комментарий в начале файла)."
        )

    updater = Updater(token=BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help_cmd))

    log.info("Бот запущен, polling...")
    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()