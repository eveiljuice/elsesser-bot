import logging
import aiosqlite
from datetime import datetime, timedelta
from typing import Optional, List, Dict

DATABASE_NAME = 'bot_database.db'
logger = logging.getLogger(__name__)


# ==================== Event Types ====================
class EventType:
    """Типы событий для аналитики"""
    START_COMMAND = 'start_command'           # /start
    PAYMENT_BUTTON_CLICKED = 'payment_btn'    # Нажал "Я оплатил(а)"
    SCREENSHOT_SENT = 'screenshot_sent'       # Прислал скриншот
    PAYMENT_APPROVED = 'payment_approved'     # Оплата подтверждена
    PAYMENT_REJECTED = 'payment_rejected'     # Оплата отклонена
    CALCULATOR_STARTED = 'calc_started'       # Начал калькулятор
    CALCULATOR_FINISHED = 'calc_finished'     # Закончил калькулятор
    RATION_VIEWED = 'ration_viewed'           # Просмотрел рацион


async def init_db():
    """Инициализация базы данных"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                has_paid INTEGER DEFAULT 0,
                payment_request_date TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS payment_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                status TEXT CHECK(status IN ('pending', 'approved', 'rejected')) DEFAULT 'pending',
                admin_message_id INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        ''')
        # Таблица для хранения рецептов (редактируемых через админку)
        await db.execute('''
            CREATE TABLE IF NOT EXISTS recipes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                calories INTEGER NOT NULL,
                day INTEGER NOT NULL,
                meal_type TEXT CHECK(meal_type IN ('breakfast', 'lunch', 'dinner')) NOT NULL,
                content TEXT NOT NULL,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_by TEXT,
                UNIQUE(calories, day, meal_type)
            )
        ''')
        # Таблица для результатов калькулятора калорий
        await db.execute('''
            CREATE TABLE IF NOT EXISTS calculator_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                gender TEXT,
                age INTEGER,
                height REAL,
                weight REAL,
                steps INTEGER,
                cardio INTEGER,
                strength INTEGER,
                goal TEXT,
                hormones TEXT,
                level TEXT,
                calories REAL,
                protein INTEGER,
                fats INTEGER,
                carbs REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        ''')
        
        # ==================== Таблица событий для аналитики ====================
        await db.execute('''
            CREATE TABLE IF NOT EXISTS user_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                metadata TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        ''')
        
        # ==================== Таблица follow-up сообщений ====================
        await db.execute('''
            CREATE TABLE IF NOT EXISTS followup_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                message_type TEXT NOT NULL,
                scheduled_at TEXT NOT NULL,
                sent_at TEXT,
                status TEXT CHECK(status IN ('pending', 'sent', 'cancelled', 'failed')) DEFAULT 'pending',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        ''')
        
        # Индекс для быстрого поиска событий по типу
        await db.execute('''
            CREATE INDEX IF NOT EXISTS idx_user_events_type 
            ON user_events(event_type, created_at)
        ''')
        
        # Индекс для follow-up сообщений
        await db.execute('''
            CREATE INDEX IF NOT EXISTS idx_followup_pending 
            ON followup_messages(status, scheduled_at)
        ''')
        
        await db.commit()


async def add_user(user_id: int, username: Optional[str], first_name: Optional[str]):
    """Добавить пользователя в БД (или обновить если существует)"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute('''
            INSERT INTO users (user_id, username, first_name)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name
        ''', (user_id, username, first_name))
        await db.commit()


async def get_user(user_id: int) -> Optional[dict]:
    """Получить информацию о пользователе"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            'SELECT * FROM users WHERE user_id = ?', (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def check_payment_status(user_id: int) -> bool:
    """Проверить статус оплаты пользователя"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute(
            'SELECT has_paid FROM users WHERE user_id = ?', (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return bool(row[0]) if row else False


async def set_payment_status(user_id: int, status: bool):
    """Установить статус оплаты пользователя"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute(
            'UPDATE users SET has_paid = ? WHERE user_id = ?',
            (1 if status else 0, user_id)
        )
        await db.commit()


async def create_payment_request(user_id: int, admin_message_id: int) -> int:
    """Создать запрос на оплату, вернуть ID запроса"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        # Обновляем дату запроса у пользователя
        await db.execute(
            'UPDATE users SET payment_request_date = ? WHERE user_id = ?',
            (datetime.now().isoformat(), user_id)
        )
        # Создаём запрос
        cursor = await db.execute('''
            INSERT INTO payment_requests (user_id, admin_message_id, status)
            VALUES (?, ?, 'pending')
        ''', (user_id, admin_message_id))
        await db.commit()
        return cursor.lastrowid


async def get_payment_request(request_id: int) -> Optional[dict]:
    """Получить информацию о запросе на оплату"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            'SELECT * FROM payment_requests WHERE id = ?', (request_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def update_payment_request(request_id: int, status: str):
    """Обновить статус запроса на оплату"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute(
            'UPDATE payment_requests SET status = ? WHERE id = ?',
            (status, request_id)
        )
        await db.commit()


async def has_pending_request(user_id: int) -> bool:
    """Проверить, есть ли у пользователя необработанный запрос"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM payment_requests WHERE user_id = ? AND status = 'pending'",
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] > 0 if row else False


# ==================== Recipes ====================

async def get_recipe(calories: int, day: int, meal_type: str) -> Optional[str]:
    """Получить рецепт из БД"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute(
            'SELECT content FROM recipes WHERE calories = ? AND day = ? AND meal_type = ?',
            (calories, day, meal_type)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None


async def save_recipe(calories: int, day: int, meal_type: str, content: str, updated_by: str):
    """Сохранить или обновить рецепт в БД"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute('''
            INSERT INTO recipes (calories, day, meal_type, content, updated_at, updated_by)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(calories, day, meal_type) DO UPDATE SET
                content = excluded.content,
                updated_at = excluded.updated_at,
                updated_by = excluded.updated_by
        ''', (calories, day, meal_type, content, datetime.now().isoformat(), updated_by))
        await db.commit()


async def get_all_custom_recipes() -> list:
    """Получить все кастомные рецепты из БД"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            'SELECT * FROM recipes ORDER BY calories, day, meal_type'
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def delete_recipe(calories: int, day: int, meal_type: str) -> bool:
    """Удалить кастомный рецепт (вернётся к дефолтному)"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        cursor = await db.execute(
            'DELETE FROM recipes WHERE calories = ? AND day = ? AND meal_type = ?',
            (calories, day, meal_type)
        )
        await db.commit()
        return cursor.rowcount > 0


# ==================== Calculator Results ====================

async def save_calculator_result(
    user_id: int,
    gender: str,
    age: int,
    height: float,
    weight: float,
    steps: int,
    cardio: int,
    strength: int,
    goal: str,
    hormones: str,
    level: str,
    calories: float,
    protein: int,
    fats: int,
    carbs: float
):
    """Сохранить результаты калькулятора калорий"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute('''
            INSERT INTO calculator_results 
            (user_id, gender, age, height, weight, steps, cardio, strength, 
             goal, hormones, level, calories, protein, fats, carbs, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_id, gender, age, height, weight, steps, cardio, strength,
            goal, hormones, level, calories, protein, fats, carbs,
            datetime.now().isoformat()
        ))
        await db.commit()


async def get_last_calculator_result(user_id: int) -> Optional[dict]:
    """Получить последний результат калькулятора для пользователя"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            'SELECT * FROM calculator_results WHERE user_id = ? ORDER BY created_at DESC LIMIT 1',
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def has_calculator_result(user_id: int) -> bool:
    """Проверить, проходил ли пользователь калькулятор"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute(
            'SELECT COUNT(*) FROM calculator_results WHERE user_id = ?',
            (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] > 0 if row else False


# ==================== User Events (Analytics) ====================

async def log_event(user_id: int, event_type: str, metadata: str = None):
    """Записать событие пользователя для аналитики (не критично - ошибки не ломают бота)"""
    try:
        async with aiosqlite.connect(DATABASE_NAME) as db:
            await db.execute('''
                INSERT INTO user_events (user_id, event_type, metadata, created_at)
                VALUES (?, ?, ?, ?)
            ''', (user_id, event_type, metadata, datetime.now().isoformat()))
            await db.commit()
    except Exception as e:
        # Логирование не критично - не ломаем работу бота
        logger.warning(f"Failed to log event {event_type} for user {user_id}: {e}")


async def get_stats() -> Dict:
    """Получить расширенную статистику для админки"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        stats = {}
        
        # 1. Всего пользователей
        async with db.execute('SELECT COUNT(*) FROM users') as cursor:
            row = await cursor.fetchone()
            stats['total_users'] = row[0] if row else 0
        
        # 2. Оплатившие пользователи
        async with db.execute('SELECT COUNT(*) FROM users WHERE has_paid = 1') as cursor:
            row = await cursor.fetchone()
            stats['paid_users'] = row[0] if row else 0
        
        # 3. Пользователи с pending запросом
        async with db.execute(
            "SELECT COUNT(DISTINCT user_id) FROM payment_requests WHERE status = 'pending'"
        ) as cursor:
            row = await cursor.fetchone()
            stats['pending_payments'] = row[0] if row else 0
        
        # 4. Сколько нажали /start
        async with db.execute(
            "SELECT COUNT(DISTINCT user_id) FROM user_events WHERE event_type = ?",
            (EventType.START_COMMAND,)
        ) as cursor:
            row = await cursor.fetchone()
            stats['started_users'] = row[0] if row else 0
        
        # 5. Сколько нажали "Я оплатил(а)"
        async with db.execute(
            "SELECT COUNT(DISTINCT user_id) FROM user_events WHERE event_type = ?",
            (EventType.PAYMENT_BUTTON_CLICKED,)
        ) as cursor:
            row = await cursor.fetchone()
            stats['clicked_payment_btn'] = row[0] if row else 0
        
        # 6. Сколько прислали скриншот
        async with db.execute(
            "SELECT COUNT(DISTINCT user_id) FROM user_events WHERE event_type = ?",
            (EventType.SCREENSHOT_SENT,)
        ) as cursor:
            row = await cursor.fetchone()
            stats['sent_screenshot'] = row[0] if row else 0
        
        # 7. Пользователи, которые ТОЛЬКО нажали /start (ничего больше не делали)
        async with db.execute('''
            SELECT COUNT(*) FROM users u
            WHERE u.has_paid = 0
            AND NOT EXISTS (
                SELECT 1 FROM user_events e 
                WHERE e.user_id = u.user_id 
                AND e.event_type IN (?, ?, ?)
            )
        ''', (EventType.PAYMENT_BUTTON_CLICKED, EventType.SCREENSHOT_SENT, EventType.CALCULATOR_STARTED)) as cursor:
            row = await cursor.fetchone()
            stats['only_start'] = row[0] if row else 0
        
        # 8. Пользователи, которые нажали "Я оплатил(а)" но НЕ прислали скрин
        async with db.execute('''
            SELECT COUNT(DISTINCT e1.user_id) FROM user_events e1
            WHERE e1.event_type = ?
            AND NOT EXISTS (
                SELECT 1 FROM user_events e2
                WHERE e2.user_id = e1.user_id
                AND e2.event_type = ?
            )
        ''', (EventType.PAYMENT_BUTTON_CLICKED, EventType.SCREENSHOT_SENT)) as cursor:
            row = await cursor.fetchone()
            stats['clicked_but_no_screenshot'] = row[0] if row else 0
            
        # 9. Статистика за последние 7 дней
        week_ago = (datetime.now() - timedelta(days=7)).isoformat()
        async with db.execute(
            'SELECT COUNT(*) FROM users WHERE created_at >= ?', (week_ago,)
        ) as cursor:
            row = await cursor.fetchone()
            stats['new_users_7d'] = row[0] if row else 0
            
        async with db.execute('''
            SELECT COUNT(*) FROM users 
            WHERE has_paid = 1 AND payment_request_date >= ?
        ''', (week_ago,)) as cursor:
            row = await cursor.fetchone()
            stats['paid_7d'] = row[0] if row else 0
        
        # ==================== Follow-up статистика ====================
        
        # 10. Всего отправлено follow-up сообщений
        async with db.execute(
            "SELECT COUNT(*) FROM followup_messages WHERE status = 'sent'"
        ) as cursor:
            row = await cursor.fetchone()
            stats['followup_sent'] = row[0] if row else 0
        
        # 11. Уникальных пользователей получили follow-up
        async with db.execute(
            "SELECT COUNT(DISTINCT user_id) FROM followup_messages WHERE status = 'sent'"
        ) as cursor:
            row = await cursor.fetchone()
            stats['followup_users'] = row[0] if row else 0
        
        # 12. Оплатили ПОСЛЕ получения follow-up
        # (пользователь получил follow-up и потом оплатил)
        async with db.execute('''
            SELECT COUNT(DISTINCT f.user_id) 
            FROM followup_messages f
            JOIN users u ON f.user_id = u.user_id
            WHERE f.status = 'sent'
            AND u.has_paid = 1
            AND u.payment_request_date > f.sent_at
        ''') as cursor:
            row = await cursor.fetchone()
            stats['paid_after_followup'] = row[0] if row else 0
        
        # 13. Проигнорировали follow-up (получили, но не оплатили)
        async with db.execute('''
            SELECT COUNT(DISTINCT f.user_id) 
            FROM followup_messages f
            JOIN users u ON f.user_id = u.user_id
            WHERE f.status = 'sent'
            AND u.has_paid = 0
        ''') as cursor:
            row = await cursor.fetchone()
            stats['ignored_followup'] = row[0] if row else 0
        
        # 14. Статистика по типам follow-up
        async with db.execute('''
            SELECT message_type, COUNT(*) as cnt
            FROM followup_messages 
            WHERE status = 'sent'
            GROUP BY message_type
        ''') as cursor:
            rows = await cursor.fetchall()
            stats['followup_by_type'] = {row[0]: row[1] for row in rows}
        
        return stats


async def get_users_for_followup(followup_type: str) -> List[Dict]:
    """
    Получить пользователей для follow-up сообщений
    
    followup_type:
    - 'only_start': нажали /start более 24ч назад и ничего не делали
    - 'clicked_payment': нажали "Я оплатил(а)" более 2ч назад, но не прислали скрин
    """
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row
        
        if followup_type == 'only_start':
            # Пользователи, которые нажали /start 24+ часов назад и ничего не делали
            cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
            async with db.execute('''
                SELECT u.user_id, u.username, u.first_name, u.created_at
                FROM users u
                WHERE u.has_paid = 0
                AND u.created_at <= ?
                AND NOT EXISTS (
                    SELECT 1 FROM user_events e 
                    WHERE e.user_id = u.user_id 
                    AND e.event_type IN (?, ?)
                )
                AND NOT EXISTS (
                    SELECT 1 FROM followup_messages f
                    WHERE f.user_id = u.user_id
                    AND f.message_type = 'only_start'
                    AND f.status IN ('sent', 'pending')
                )
            ''', (cutoff, EventType.PAYMENT_BUTTON_CLICKED, EventType.SCREENSHOT_SENT)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
                
        elif followup_type == 'clicked_payment':
            # Пользователи, которые нажали "Я оплатил(а)" 2+ часа назад, но не прислали скрин
            cutoff = (datetime.now() - timedelta(hours=2)).isoformat()
            async with db.execute('''
                SELECT DISTINCT u.user_id, u.username, u.first_name, e.created_at as event_at
                FROM users u
                JOIN user_events e ON u.user_id = e.user_id
                WHERE u.has_paid = 0
                AND e.event_type = ?
                AND e.created_at <= ?
                AND NOT EXISTS (
                    SELECT 1 FROM user_events e2
                    WHERE e2.user_id = u.user_id
                    AND e2.event_type = ?
                )
                AND NOT EXISTS (
                    SELECT 1 FROM followup_messages f
                    WHERE f.user_id = u.user_id
                    AND f.message_type = 'clicked_payment'
                    AND f.status IN ('sent', 'pending')
                )
            ''', (EventType.PAYMENT_BUTTON_CLICKED, cutoff, EventType.SCREENSHOT_SENT)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
        
        return []


async def schedule_followup(user_id: int, message_type: str, scheduled_at: datetime):
    """Запланировать follow-up сообщение"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute('''
            INSERT INTO followup_messages (user_id, message_type, scheduled_at, status, created_at)
            VALUES (?, ?, ?, 'pending', ?)
        ''', (user_id, message_type, scheduled_at.isoformat(), datetime.now().isoformat()))
        await db.commit()


async def get_pending_followups() -> List[Dict]:
    """Получить все pending follow-up сообщения, которые пора отправить"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row
        now = datetime.now().isoformat()
        async with db.execute('''
            SELECT f.*, u.username, u.first_name, u.has_paid
            FROM followup_messages f
            JOIN users u ON f.user_id = u.user_id
            WHERE f.status = 'pending'
            AND f.scheduled_at <= ?
        ''', (now,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def mark_followup_sent(followup_id: int, status: str = 'sent'):
    """Отметить follow-up как отправленный или неудачный"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute('''
            UPDATE followup_messages 
            SET status = ?, sent_at = ?
            WHERE id = ?
        ''', (status, datetime.now().isoformat(), followup_id))
        await db.commit()


async def cancel_user_followups(user_id: int):
    """Отменить все pending follow-up для пользователя (например, после оплаты)"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute('''
            UPDATE followup_messages 
            SET status = 'cancelled'
            WHERE user_id = ? AND status = 'pending'
        ''', (user_id,))
        await db.commit()


async def get_weekly_report() -> Dict:
    """
    Получить детальный недельный отчёт для модераторов.
    Включает статистику за последние 7 дней.
    """
    async with aiosqlite.connect(DATABASE_NAME) as db:
        report = {}
        week_ago = (datetime.now() - timedelta(days=7)).isoformat()
        
        # === ОБЩАЯ СТАТИСТИКА ===
        
        # Всего пользователей
        async with db.execute('SELECT COUNT(*) FROM users') as cursor:
            row = await cursor.fetchone()
            report['total_users'] = row[0] if row else 0
        
        # Всего оплативших
        async with db.execute('SELECT COUNT(*) FROM users WHERE has_paid = 1') as cursor:
            row = await cursor.fetchone()
            report['total_paid'] = row[0] if row else 0
        
        # === СТАТИСТИКА ЗА НЕДЕЛЮ ===
        
        # Новых пользователей за неделю
        async with db.execute(
            'SELECT COUNT(*) FROM users WHERE created_at >= ?', (week_ago,)
        ) as cursor:
            row = await cursor.fetchone()
            report['new_users_week'] = row[0] if row else 0
        
        # Оплатили за неделю
        async with db.execute('''
            SELECT COUNT(*) FROM users 
            WHERE has_paid = 1 AND payment_request_date >= ?
        ''', (week_ago,)) as cursor:
            row = await cursor.fetchone()
            report['paid_week'] = row[0] if row else 0
        
        # Всего запросов на оплату за неделю
        async with db.execute(
            "SELECT COUNT(*) FROM payment_requests WHERE created_at >= ?", (week_ago,)
        ) as cursor:
            row = await cursor.fetchone()
            report['payment_requests_week'] = row[0] if row else 0
        
        # Одобрено за неделю
        async with db.execute(
            "SELECT COUNT(*) FROM payment_requests WHERE status = 'approved' AND created_at >= ?", 
            (week_ago,)
        ) as cursor:
            row = await cursor.fetchone()
            report['approved_week'] = row[0] if row else 0
        
        # Отклонено за неделю
        async with db.execute(
            "SELECT COUNT(*) FROM payment_requests WHERE status = 'rejected' AND created_at >= ?", 
            (week_ago,)
        ) as cursor:
            row = await cursor.fetchone()
            report['rejected_week'] = row[0] if row else 0
        
        # Ожидают проверки (всего)
        async with db.execute(
            "SELECT COUNT(*) FROM payment_requests WHERE status = 'pending'"
        ) as cursor:
            row = await cursor.fetchone()
            report['pending_now'] = row[0] if row else 0
        
        # === ВОРОНКА ЗА НЕДЕЛЮ ===
        
        # Нажали /start за неделю
        async with db.execute(
            "SELECT COUNT(DISTINCT user_id) FROM user_events WHERE event_type = ? AND created_at >= ?",
            (EventType.START_COMMAND, week_ago)
        ) as cursor:
            row = await cursor.fetchone()
            report['started_week'] = row[0] if row else 0
        
        # Нажали "Я оплатила" за неделю
        async with db.execute(
            "SELECT COUNT(DISTINCT user_id) FROM user_events WHERE event_type = ? AND created_at >= ?",
            (EventType.PAYMENT_BUTTON_CLICKED, week_ago)
        ) as cursor:
            row = await cursor.fetchone()
            report['clicked_payment_week'] = row[0] if row else 0
        
        # Прислали скриншот за неделю
        async with db.execute(
            "SELECT COUNT(DISTINCT user_id) FROM user_events WHERE event_type = ? AND created_at >= ?",
            (EventType.SCREENSHOT_SENT, week_ago)
        ) as cursor:
            row = await cursor.fetchone()
            report['screenshot_week'] = row[0] if row else 0
        
        # === FOLLOW-UP СТАТИСТИКА ЗА НЕДЕЛЮ ===
        
        # Отправлено follow-up за неделю
        async with db.execute(
            "SELECT COUNT(*) FROM followup_messages WHERE status = 'sent' AND sent_at >= ?",
            (week_ago,)
        ) as cursor:
            row = await cursor.fetchone()
            report['followup_sent_week'] = row[0] if row else 0
        
        # Оплатили после follow-up за неделю
        async with db.execute('''
            SELECT COUNT(DISTINCT f.user_id) 
            FROM followup_messages f
            JOIN users u ON f.user_id = u.user_id
            WHERE f.status = 'sent'
            AND f.sent_at >= ?
            AND u.has_paid = 1
            AND u.payment_request_date > f.sent_at
        ''', (week_ago,)) as cursor:
            row = await cursor.fetchone()
            report['paid_after_followup_week'] = row[0] if row else 0
        
        # === КАЛЬКУЛЯТОР ЗА НЕДЕЛЮ ===
        
        # Прошли калькулятор за неделю
        async with db.execute(
            "SELECT COUNT(DISTINCT user_id) FROM calculator_results WHERE created_at >= ?",
            (week_ago,)
        ) as cursor:
            row = await cursor.fetchone()
            report['calculator_completed_week'] = row[0] if row else 0
        
        # === ПОТЕРЯННЫЕ КЛИЕНТЫ ===
        
        # Только /start (ничего не делали) — всего
        async with db.execute('''
            SELECT COUNT(*) FROM users u
            WHERE u.has_paid = 0
            AND NOT EXISTS (
                SELECT 1 FROM user_events e 
                WHERE e.user_id = u.user_id 
                AND e.event_type IN (?, ?, ?)
            )
        ''', (EventType.PAYMENT_BUTTON_CLICKED, EventType.SCREENSHOT_SENT, EventType.CALCULATOR_STARTED)) as cursor:
            row = await cursor.fetchone()
            report['only_start_total'] = row[0] if row else 0
        
        # Нажали оплату, но без скрина — всего
        async with db.execute('''
            SELECT COUNT(DISTINCT e1.user_id) FROM user_events e1
            WHERE e1.event_type = ?
            AND NOT EXISTS (
                SELECT 1 FROM user_events e2
                WHERE e2.user_id = e1.user_id
                AND e2.event_type = ?
            )
        ''', (EventType.PAYMENT_BUTTON_CLICKED, EventType.SCREENSHOT_SENT)) as cursor:
            row = await cursor.fetchone()
            report['clicked_no_screenshot_total'] = row[0] if row else 0
        
        # === ТОП ДНЕЙ НЕДЕЛИ ПО ОПЛАТАМ ===
        
        async with db.execute('''
            SELECT strftime('%w', payment_request_date) as weekday, COUNT(*) as cnt
            FROM users 
            WHERE has_paid = 1 AND payment_request_date >= ?
            GROUP BY weekday
            ORDER BY cnt DESC
        ''', (week_ago,)) as cursor:
            rows = await cursor.fetchall()
            weekdays_map = {
                '0': 'Вс', '1': 'Пн', '2': 'Вт', '3': 'Ср', 
                '4': 'Чт', '5': 'Пт', '6': 'Сб'
            }
            report['payments_by_weekday'] = {
                weekdays_map.get(row[0], row[0]): row[1] for row in rows
            }
        
        return report


async def get_users_by_status(status_type: str) -> List[Dict]:
    """
    Получить список пользователей по статусу для детальной статистики
    
    status_type:
    - 'paid': оплатившие пользователи
    - 'pending': ожидают проверки оплаты
    - 'rejected': отклонённые заявки
    - 'only_start': только нажали /start (ничего не делали)
    - 'clicked_no_screenshot': нажали оплату, но не прислали скрин
    - 'all_users': все пользователи
    """
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row
        
        if status_type == 'paid':
            # Оплатившие пользователи
            async with db.execute('''
                SELECT user_id, username, first_name, has_paid, created_at
                FROM users
                WHERE has_paid = 1
                ORDER BY payment_request_date DESC
            ''') as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
        
        elif status_type == 'pending':
            # Пользователи с pending запросами на оплату
            async with db.execute('''
                SELECT DISTINCT u.user_id, u.username, u.first_name, u.has_paid, u.created_at
                FROM users u
                JOIN payment_requests pr ON u.user_id = pr.user_id
                WHERE pr.status = 'pending'
                ORDER BY pr.created_at DESC
            ''') as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
        
        elif status_type == 'rejected':
            # Пользователи с отклонёнными запросами
            async with db.execute('''
                SELECT DISTINCT u.user_id, u.username, u.first_name, u.has_paid, u.created_at,
                       pr.created_at as request_date
                FROM users u
                JOIN payment_requests pr ON u.user_id = pr.user_id
                WHERE pr.status = 'rejected'
                ORDER BY pr.created_at DESC
            ''') as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
        
        elif status_type == 'only_start':
            # Пользователи, которые только нажали /start (ничего не делали)
            async with db.execute('''
                SELECT u.user_id, u.username, u.first_name, u.has_paid, u.created_at
                FROM users u
                WHERE u.has_paid = 0
                AND NOT EXISTS (
                    SELECT 1 FROM user_events e 
                    WHERE e.user_id = u.user_id 
                    AND e.event_type IN (?, ?, ?)
                )
                ORDER BY u.created_at DESC
            ''', (EventType.PAYMENT_BUTTON_CLICKED, EventType.SCREENSHOT_SENT, EventType.CALCULATOR_STARTED)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
        
        elif status_type == 'clicked_no_screenshot':
            # Пользователи, которые нажали "Я оплатил(а)" но не прислали скрин
            async with db.execute('''
                SELECT DISTINCT u.user_id, u.username, u.first_name, u.has_paid, u.created_at,
                       e.created_at as event_date
                FROM users u
                JOIN user_events e ON u.user_id = e.user_id
                WHERE e.event_type = ?
                AND NOT EXISTS (
                    SELECT 1 FROM user_events e2
                    WHERE e2.user_id = u.user_id
                    AND e2.event_type = ?
                )
                ORDER BY e.created_at DESC
            ''', (EventType.PAYMENT_BUTTON_CLICKED, EventType.SCREENSHOT_SENT)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
        
        elif status_type == 'all_users':
            # Все пользователи
            async with db.execute('''
                SELECT user_id, username, first_name, has_paid, created_at
                FROM users
                ORDER BY created_at DESC
            ''') as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
        
        return []