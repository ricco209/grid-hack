"""
GRID // HACK — Telegram bot launcher
Uses python-telegram-bot 13.x (synchronous API), which supports
Python 3.7+ including 3.8.10 — no asyncio/Node.js required.

Set these two environment variables before running:
  BOT_TOKEN   - token from @BotFather
  WEBAPP_URL  - your deployed URL, e.g. https://your-app.onrender.com
"""

import os
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Updater, CommandHandler, CallbackContext
from telegram import Update

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
log = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8931901950:AAGS455ThCFk61Nj9DN4C8gLI19BfDblmFc")
WEBAPP_URL = os.environ.get("WEBAPP_URL", "https://grid-hack.onrender.com")


def start(update: Update, context: CallbackContext):
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Open GRID // HACK", web_app=WebAppInfo(url=WEBAPP_URL))]]
    )
    update.message.reply_text(
        "GRID // HACK\n\n"
        "Небольшое мини-приложение: заходи, чтобы увидеть приветствие "
        "и получить случайный факт.",
        reply_markup=keyboard,
    )


def help_cmd(update: Update, context: CallbackContext):
    update.message.reply_text("/start — open the game\n/help — this message")


def main():
    if not BOT_TOKEN:
        raise SystemExit("Set the BOT_TOKEN environment variable first.")

    updater = Updater(token=BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help_cmd))

    log.info("Bot polling started.")
    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()