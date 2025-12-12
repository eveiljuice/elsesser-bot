# AGENTS.md

## Project Overview
Telegram бот для продажи рационов питания с калькулятором калорий.

**Tech Stack:**
- Python 3.10+
- aiogram 3.22 (Telegram Bot API)
- aiosqlite (async SQLite)
- APScheduler 4.x (фоновые задачи)

**Архитектура:**
- `bot.py` — точка входа, инициализация бота и scheduler
- `database.py` — все операции с БД, модели данных, аналитика
- `handlers/` — роутеры aiogram (user, admin, calculator)
- `keyboards/` — клавиатуры и callback-данные
- `data/` — рецепты и контент
- `followup.py` — система follow-up сообщений

## Dev Environment Tips

```bash
# Создать venv
python -m venv venv
venv\Scripts\activate  # Windows

# Установить зависимости
pip install -r requirements.txt

# Переменные окружения (.env)
BOT_TOKEN=your_bot_token
ADMIN_CHANNEL_ID=-100123456789
PAYMENT_AMOUNT=500
PAYMENT_DETAILS="Номер карты: 1234..."
```

## Build & Run Commands

```bash
# Запуск бота
python bot.py

# База данных создаётся автоматически при первом запуске (bot_database.db)
```

## Code Style Guidelines

- **Именование:** snake_case для функций/переменных, PascalCase для классов
- **Async:** Все DB операции и API вызовы — async/await
- **Логирование:** Использовать `logger` из logging модуля
- **HTML ParseMode:** Для форматирования сообщений Telegram
- **FSM:** aiogram FSM для многоэтапных диалогов

## Key Files Reference

| Файл | Назначение |
|------|-----------|
| `database.py` | EventType класс, log_event(), get_stats() |
| `handlers/admin.py` | Админка, статистика, верификация оплат |
| `handlers/user.py` | /start, оплата, выбор рационов |
| `followup.py` | Follow-up сообщения, шаблоны |
| `config.py` | ADMIN_USERNAMES, токены |

## Analytics Events

```python
from database import EventType

EventType.START_COMMAND      # /start
EventType.PAYMENT_BUTTON_CLICKED  # Нажал "Я оплатил(а)"
EventType.SCREENSHOT_SENT    # Прислал скрин
EventType.PAYMENT_APPROVED   # Оплата одобрена
EventType.PAYMENT_REJECTED   # Оплата отклонена
```

## Follow-up System

- Scheduler запускает задачи каждые 5 мин / 1 час
- `only_start` — пользователи, нажавшие только /start (24ч+)
- `clicked_payment` — нажали оплату, но без скрина (2ч+)
- Follow-up отменяются после оплаты (`cancel_user_followups`)

