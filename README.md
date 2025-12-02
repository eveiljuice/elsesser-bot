# Elsesser Bot 🤖

Telegram bot for a private recipe channel. Manage subscriptions, payments, and access through an admin panel.

## Stack

- **Python 3.11+**
- **aiogram 3.x** - asynchronous framework for Telegram Bot API
- **aiosqlite** - asynchronous SQLite operations
- **python-dotenv** - environment variable management

## Structure

```
├── bot.py              # Entry point
├── config.py           # Configuration (env variables)
├── database.py         # Database operations
├── handlers/
│   ├── user.py         # User handlers
│   └── admin.py        # Admin panel
├── keyboards/
│   ├── user_kb.py      # User keyboards
│   ├── admin_kb.py     # Admin keyboards
│   └── callbacks.py    # Callback factories
└── data/
    └── recipes.py      # Recipe data
```

## Environment Variables

Create a `.env` file:

```
BOT_TOKEN=your_bot_token
ADMIN_CHANNEL_ID=-100xxxxxxxxxx
PAYMENT_AMOUNT=500
PAYMENT_DETAILS=Card number: 1234 5678 9012 3456
```

## Local Setup

```
pip install -r requirements.txt
python bot.py
```

## Deploy to Render.com

1. Create a **Background Worker** (not Web Service!)
2. Connect GitHub repository
3. Configure:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python bot.py`
4. Add Environment Variables:
   - `BOT_TOKEN`
   - `ADMIN_CHANNEL_ID`
   - `PAYMENT_AMOUNT`
   - `PAYMENT_DETAILS`

## Features

**For users:**
- View demo recipes
- Pay for subscription
- Access private channel after confirmation

**For admins:**
- Review payment requests
- Approve/reject payments
- Manage users
- Statistics
```
