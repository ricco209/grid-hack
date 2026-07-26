# GRID // HACK

A small Telegram Mini App game with a "Matrix" terminal look — tap the
falling symbol that matches the target before it scrolls off the grid.
No tokens, no wallet, no referral system — just a score and a local
leaderboard.

## Project layout

```
matrix-hack/
├── app.py            # Flask backend: serves the Mini App + score API
├── bot.py             # Telegram bot: sends the "Open" button
├── requirements.txt
├── Procfile           # for Render
├── scores.db          # created automatically (SQLite)
├── static/
│   ├── index.html
│   ├── style.css
│   └── game.js
└── templates/          # (unused placeholder, kept for Flask defaults)
```

Everything is plain Flask + vanilla HTML/CSS/JS — no Node.js, no
bundler, no build step. This keeps it workable on an older machine
(Windows 7 x64, Python 3.8.10, PyCharm 2020.1.4).

## 1. Local setup in PyCharm 2020.1.4

1. Open the `matrix-hack` folder as a PyCharm project.
2. `File → Settings → Project → Python Interpreter → Add → Virtualenv`,
   base interpreter: your Python 3.8.10 install.
3. Open the Terminal tab in PyCharm and install dependencies:
   ```
   pip install -r requirements.txt
   ```
4. Run the web app locally:
   ```
   python app.py
   ```
   It serves on `http://localhost:5000`. Open it in a normal browser
   to test the game outside Telegram (it falls back to a guest user).

## 2. Deploy the web app to Render

1. Push this folder to a GitHub repo.
2. On Render: **New → Web Service**, connect the repo.
3. Runtime: Python 3. Build command: `pip install -r requirements.txt`.
   Start command is already in `Procfile` (`gunicorn app:app`).
4. Once deployed you'll get a URL like `https://your-app.onrender.com`.
   That's your `WEBAPP_URL`.

Note: Render's free tier uses an ephemeral filesystem, so `scores.db`
resets on redeploy/restart. Fine for a casual game; swap in a real
database later if you want persistent leaderboards.

## 3. Run the Telegram bot

The bot only needs to send one button that opens the Mini App — it
doesn't need to run on Render at all, it can run from your own PC via
PyCharm, or as a second Render **Background Worker**.

1. Create a bot with [@BotFather](https://t.me/BotFather), grab the token.
2. In BotFather, also run `/setmenubutton` (or configure the Mini App)
   and point it at your Render URL if you want the app reachable from
   the menu button too.
3. Set environment variables (PyCharm → Run/Debug Configurations →
   Environment variables, or in Render's dashboard for a worker):
   ```
   BOT_TOKEN=123456:your-token-from-botfather
   WEBAPP_URL=https://your-app.onrender.com
   ```
4. Run:
   ```
   python bot.py
   ```
5. In Telegram, send `/start` to your bot — it replies with an
   "Open GRID // HACK" button that launches the Mini App.

## Notes on the game itself

- Score is purely in-app (an integer), stored locally on the device
  and optionally synced to `/api/score` for the shared leaderboard.
- Difficulty ramps up slowly as the player scores points (faster
  glyphs, more frequent spawns).
- No real-money or crypto claims anywhere in the copy — keep it that
  way if you extend it.
