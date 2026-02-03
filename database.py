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
                has_paid_fmd INTEGER DEFAULT 0,
                has_paid_bundle INTEGER DEFAULT 0,
                payment_request_date TEXT,
                fmd_payment_request_date TEXT,
                bundle_payment_request_date TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Миграция: добавляем поля для FMD если их нет
        try:
            await db.execute('ALTER TABLE users ADD COLUMN has_paid_fmd INTEGER DEFAULT 0')
        except:
            pass  # Колонка уже существует
        try:
            await db.execute('ALTER TABLE users ADD COLUMN fmd_payment_request_date TEXT')
        except:
            pass  # Колонка уже существует
        try:
            await db.execute('ALTER TABLE users ADD COLUMN has_paid_bundle INTEGER DEFAULT 0')
        except:
            pass  # Колонка уже существует
        try:
            await db.execute('ALTER TABLE users ADD COLUMN bundle_payment_request_date TEXT')
        except:
            pass  # Колонка уже существует
        # Миграция: добавляем поля для Сушки если их нет
        try:
            await db.execute('ALTER TABLE users ADD COLUMN has_paid_dry INTEGER DEFAULT 0')
        except:
            pass  # Колонка уже существует
        try:
            await db.execute('ALTER TABLE users ADD COLUMN dry_payment_request_date TEXT')
        except:
            pass  # Колонка уже существует
        await db.execute('''
            CREATE TABLE IF NOT EXISTS payment_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                status TEXT CHECK(status IN ('pending', 'approved', 'rejected')) DEFAULT 'pending',
                admin_message_id INTEGER,
                product_type TEXT DEFAULT 'main',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        ''')

        # Миграция: добавляем product_type если его нет
        try:
            await db.execute("ALTER TABLE payment_requests ADD COLUMN product_type TEXT DEFAULT 'main'")
        except:
            pass  # Колонка уже существует
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

        # ==================== Таблица рассылок ====================
        await db.execute('''
            CREATE TABLE IF NOT EXISTS broadcasts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                audience TEXT NOT NULL CHECK(audience IN ('all', 'start_only', 'rejected', 'no_screenshot')),
                scheduled_at TEXT NOT NULL,
                status TEXT CHECK(status IN ('pending', 'sending', 'sent', 'cancelled')) DEFAULT 'pending',
                created_by INTEGER NOT NULL,
                created_by_username TEXT,
                sent_count INTEGER DEFAULT 0,
                failed_count INTEGER DEFAULT 0,
                media_type TEXT CHECK(media_type IN ('photo', 'video', NULL)),
                media_file_id TEXT,
                buttons TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                sent_at TEXT
            )
        ''')

        # Миграция: добавляем поля для медиа и кнопок если их нет
        try:
            await db.execute('ALTER TABLE broadcasts ADD COLUMN media_type TEXT')
        except:
            pass
        try:
            await db.execute('ALTER TABLE broadcasts ADD COLUMN media_file_id TEXT')
        except:
            pass
        try:
            await db.execute('ALTER TABLE broadcasts ADD COLUMN buttons TEXT')
        except:
            pass

        # Индекс для поиска pending рассылок
        await db.execute('''
            CREATE INDEX IF NOT EXISTS idx_broadcasts_pending 
            ON broadcasts(status, scheduled_at)
        ''')

        # ==================== Таблица шаблонов рассылок ====================
        await db.execute('''
            CREATE TABLE IF NOT EXISTS broadcast_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                content TEXT NOT NULL,
                created_by INTEGER NOT NULL,
                created_by_username TEXT,
                media_type TEXT CHECK(media_type IN ('photo', 'video', NULL)),
                media_file_id TEXT,
                buttons TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Миграция: добавляем поля для медиа и кнопок если их нет
        try:
            await db.execute('ALTER TABLE broadcast_templates ADD COLUMN media_type TEXT')
        except:
            pass
        try:
            await db.execute('ALTER TABLE broadcast_templates ADD COLUMN media_file_id TEXT')
        except:
            pass
        try:
            await db.execute('ALTER TABLE broadcast_templates ADD COLUMN buttons TEXT')
        except:
            pass

        # ==================== Таблица автоматических рассылок ====================
        await db.execute('''
            CREATE TABLE IF NOT EXISTS auto_broadcasts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trigger_type TEXT NOT NULL CHECK(trigger_type IN ('only_start', 'no_payment', 'rejected', 'no_screenshot')),
                content TEXT NOT NULL,
                delay_hours INTEGER NOT NULL DEFAULT 24,
                is_active INTEGER DEFAULT 1,
                created_by INTEGER NOT NULL,
                created_by_username TEXT,
                sent_count INTEGER DEFAULT 0,
                media_type TEXT CHECK(media_type IN ('photo', 'video', NULL)),
                media_file_id TEXT,
                buttons TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Миграция: добавляем поля для медиа и кнопок если их нет
        try:
            await db.execute('ALTER TABLE auto_broadcasts ADD COLUMN media_type TEXT')
        except:
            pass
        try:
            await db.execute('ALTER TABLE auto_broadcasts ADD COLUMN media_file_id TEXT')
        except:
            pass
        try:
            await db.execute('ALTER TABLE auto_broadcasts ADD COLUMN buttons TEXT')
        except:
            pass

        # Таблица для отслеживания уже отправленных авто-рассылок
        await db.execute('''
            CREATE TABLE IF NOT EXISTS auto_broadcast_sent (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                auto_broadcast_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                sent_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(auto_broadcast_id, user_id),
                FOREIGN KEY(auto_broadcast_id) REFERENCES auto_broadcasts(id),
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
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
    """Проверить статус оплаты пользователя (основной рацион)"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute(
            'SELECT has_paid FROM users WHERE user_id = ?', (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return bool(row[0]) if row else False


async def set_payment_status(user_id: int, status: bool):
    """Установить статус оплаты пользователя (основной рацион)"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute(
            'UPDATE users SET has_paid = ? WHERE user_id = ?',
            (1 if status else 0, user_id)
        )
        await db.commit()


async def check_fmd_payment_status(user_id: int) -> bool:
    """Проверить статус оплаты FMD протокола"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute(
            'SELECT has_paid_fmd FROM users WHERE user_id = ?', (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return bool(row[0]) if row else False


async def set_fmd_payment_status(user_id: int, status: bool):
    """Установить статус оплаты FMD протокола"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute(
            'UPDATE users SET has_paid_fmd = ? WHERE user_id = ?',
            (1 if status else 0, user_id)
        )
        await db.commit()


async def check_bundle_payment_status(user_id: int) -> bool:
    """Проверить статус оплаты комплекта (Рационы + FMD)"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute(
            'SELECT has_paid_bundle FROM users WHERE user_id = ?', (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return bool(row[0]) if row else False


async def set_bundle_payment_status(user_id: int, status: bool):
    """Установить статус оплаты комплекта (Рационы + FMD)

    При активации комплекта также активирует доступ к основным рационам и FMD
    """
    async with aiosqlite.connect(DATABASE_NAME) as db:
        if status:
            # При оплате комплекта даём доступ ко всем продуктам
            await db.execute(
                'UPDATE users SET has_paid_bundle = 1, has_paid = 1, has_paid_fmd = 1 WHERE user_id = ?',
                (user_id,)
            )
        else:
            await db.execute(
                'UPDATE users SET has_paid_bundle = 0 WHERE user_id = ?',
                (user_id,)
            )
        await db.commit()


async def check_dry_payment_status(user_id: int) -> bool:
    """Проверить статус оплаты Сушки"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute(
            'SELECT has_paid_dry FROM users WHERE user_id = ?', (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return bool(row[0]) if row else False


async def set_dry_payment_status(user_id: int, status: bool):
    """Установить статус оплаты Сушки"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute(
            'UPDATE users SET has_paid_dry = ? WHERE user_id = ?',
            (1 if status else 0, user_id)
        )
        await db.commit()


async def create_payment_request(user_id: int, admin_message_id: int, product_type: str = 'main') -> int:
    """Создать запрос на оплату, вернуть ID запроса

    product_type: 'main' - основной рацион, 'fmd' - FMD протокол, 'bundle' - комплект, 'dry' - Сушка
    """
    async with aiosqlite.connect(DATABASE_NAME) as db:
        # Обновляем дату запроса у пользователя
        if product_type == 'fmd':
            await db.execute(
                'UPDATE users SET fmd_payment_request_date = ? WHERE user_id = ?',
                (datetime.now().isoformat(), user_id)
            )
        elif product_type == 'bundle':
            await db.execute(
                'UPDATE users SET bundle_payment_request_date = ? WHERE user_id = ?',
                (datetime.now().isoformat(), user_id)
            )
        elif product_type == 'dry':
            await db.execute(
                'UPDATE users SET dry_payment_request_date = ? WHERE user_id = ?',
                (datetime.now().isoformat(), user_id)
            )
        else:
            await db.execute(
                'UPDATE users SET payment_request_date = ? WHERE user_id = ?',
                (datetime.now().isoformat(), user_id)
            )
        # Создаём запрос
        cursor = await db.execute('''
            INSERT INTO payment_requests (user_id, admin_message_id, status, product_type)
            VALUES (?, ?, 'pending', ?)
        ''', (user_id, admin_message_id, product_type))
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


async def has_pending_request(user_id: int, product_type: str = None) -> bool:
    """Проверить, есть ли у пользователя необработанный запрос

    product_type: None - любой продукт, 'main' - основной рацион, 'fmd' - FMD протокол
    """
    async with aiosqlite.connect(DATABASE_NAME) as db:
        if product_type:
            async with db.execute(
                "SELECT COUNT(*) FROM payment_requests WHERE user_id = ? AND status = 'pending' AND product_type = ?",
                (user_id, product_type)
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] > 0 if row else False
        else:
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
        logger.warning(
            f"Failed to log event {event_type} for user {user_id}: {e}")


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


# ==================== Broadcast Management ====================

async def create_broadcast(
    content: str,
    audience: str,
    scheduled_at: datetime,
    created_by: int,
    created_by_username: str = None,
    media_type: str = None,
    media_file_id: str = None,
    buttons: str = None
) -> int:
    """Создать новую рассылку, вернуть ID"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        cursor = await db.execute('''
            INSERT INTO broadcasts (content, audience, scheduled_at, created_by, created_by_username, status, media_type, media_file_id, buttons, created_at)
            VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?)
        ''', (content, audience, scheduled_at.isoformat(), created_by, created_by_username, media_type, media_file_id, buttons, datetime.now().isoformat()))
        await db.commit()
        return cursor.lastrowid


async def get_broadcast(broadcast_id: int) -> Optional[Dict]:
    """Получить информацию о рассылке"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            'SELECT * FROM broadcasts WHERE id = ?', (broadcast_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def get_pending_broadcasts() -> List[Dict]:
    """Получить все pending рассылки, которые пора отправить"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row
        now = datetime.now().isoformat()
        async with db.execute('''
            SELECT * FROM broadcasts
            WHERE status = 'pending'
            AND scheduled_at <= ?
            ORDER BY scheduled_at ASC
        ''', (now,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def get_scheduled_broadcasts() -> List[Dict]:
    """Получить все запланированные рассылки для отображения в админке"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('''
            SELECT * FROM broadcasts
            WHERE status = 'pending'
            ORDER BY scheduled_at ASC
        ''') as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def update_broadcast_status(broadcast_id: int, status: str, sent_count: int = 0, failed_count: int = 0):
    """Обновить статус рассылки"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        if status == 'sent':
            await db.execute('''
                UPDATE broadcasts 
                SET status = ?, sent_count = ?, failed_count = ?, sent_at = ?
                WHERE id = ?
            ''', (status, sent_count, failed_count, datetime.now().isoformat(), broadcast_id))
        else:
            await db.execute('''
                UPDATE broadcasts 
                SET status = ?
                WHERE id = ?
            ''', (status, broadcast_id))
        await db.commit()


async def cancel_broadcast(broadcast_id: int) -> bool:
    """Отменить рассылку (только если pending)"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        cursor = await db.execute('''
            UPDATE broadcasts 
            SET status = 'cancelled'
            WHERE id = ? AND status = 'pending'
        ''', (broadcast_id,))
        await db.commit()
        return cursor.rowcount > 0


async def get_broadcast_audience_users(audience: str) -> List[Dict]:
    """
    Получить пользователей для рассылки по типу аудитории

    audience:
    - 'all': все пользователи
    - 'start_only': только нажали /start (ничего не делали)
    - 'rejected': с отклонёнными заявками
    - 'no_screenshot': нажали оплату, но не прислали скрин
    """
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row

        if audience == 'all':
            # Все пользователи
            async with db.execute('''
                SELECT user_id, username, first_name
                FROM users
            ''') as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

        elif audience == 'start_only':
            # Пользователи, которые только нажали /start (ничего не делали)
            async with db.execute('''
                SELECT u.user_id, u.username, u.first_name
                FROM users u
                WHERE u.has_paid = 0
                AND NOT EXISTS (
                    SELECT 1 FROM user_events e 
                    WHERE e.user_id = u.user_id 
                    AND e.event_type IN (?, ?, ?)
                )
            ''', (EventType.PAYMENT_BUTTON_CLICKED, EventType.SCREENSHOT_SENT, EventType.CALCULATOR_STARTED)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

        elif audience == 'rejected':
            # Пользователи с отклонёнными запросами (и не оплатившие после)
            async with db.execute('''
                SELECT DISTINCT u.user_id, u.username, u.first_name
                FROM users u
                JOIN payment_requests pr ON u.user_id = pr.user_id
                WHERE pr.status = 'rejected'
                AND u.has_paid = 0
            ''') as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

        elif audience == 'no_screenshot':
            # Пользователи, которые нажали "Я оплатил(а)" но не прислали скрин
            async with db.execute('''
                SELECT DISTINCT u.user_id, u.username, u.first_name
                FROM users u
                JOIN user_events e ON u.user_id = e.user_id
                WHERE e.event_type = ?
                AND u.has_paid = 0
                AND NOT EXISTS (
                    SELECT 1 FROM user_events e2
                    WHERE e2.user_id = u.user_id
                    AND e2.event_type = ?
                )
            ''', (EventType.PAYMENT_BUTTON_CLICKED, EventType.SCREENSHOT_SENT)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

        return []


async def get_broadcast_audience_count(audience: str) -> int:
    """Получить количество пользователей для аудитории рассылки"""
    users = await get_broadcast_audience_users(audience)
    return len(users)


# ==================== Template Management ====================

async def create_template(
    content: str,
    created_by: int,
    created_by_username: str = None,
    name: str = None,
    media_type: str = None,
    media_file_id: str = None,
    buttons: str = None
) -> int:
    """Создать шаблон рассылки"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        cursor = await db.execute('''
            INSERT INTO broadcast_templates (name, content, created_by, created_by_username, media_type, media_file_id, buttons)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (name, content, created_by, created_by_username, media_type, media_file_id, buttons))
        await db.commit()
        return cursor.lastrowid


async def get_templates(created_by: int = None) -> List[Dict]:
    """Получить все шаблоны (или только конкретного пользователя)"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row

        if created_by:
            async with db.execute('''
                SELECT * FROM broadcast_templates 
                WHERE created_by = ?
                ORDER BY created_at DESC
            ''', (created_by,)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
        else:
            async with db.execute('''
                SELECT * FROM broadcast_templates 
                ORDER BY created_at DESC
            ''') as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]


async def get_template(template_id: int) -> Optional[Dict]:
    """Получить конкретный шаблон"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('''
            SELECT * FROM broadcast_templates WHERE id = ?
        ''', (template_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def delete_template(template_id: int) -> bool:
    """Удалить шаблон"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        cursor = await db.execute('''
            DELETE FROM broadcast_templates WHERE id = ?
        ''', (template_id,))
        await db.commit()
        return cursor.rowcount > 0


# ==================== Auto-Broadcast Management ====================

async def create_auto_broadcast(
    trigger_type: str,
    content: str,
    delay_hours: int,
    created_by: int,
    created_by_username: str = None,
    media_type: str = None,
    media_file_id: str = None,
    buttons: str = None
) -> int:
    """Создать автоматическую рассылку"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        cursor = await db.execute('''
            INSERT INTO auto_broadcasts (trigger_type, content, delay_hours, created_by, created_by_username, media_type, media_file_id, buttons)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (trigger_type, content, delay_hours, created_by, created_by_username, media_type, media_file_id, buttons))
        await db.commit()
        return cursor.lastrowid


async def get_auto_broadcasts(active_only: bool = False) -> List[Dict]:
    """Получить все автоматические рассылки"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row

        if active_only:
            async with db.execute('''
                SELECT * FROM auto_broadcasts 
                WHERE is_active = 1
                ORDER BY created_at DESC
            ''') as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
        else:
            async with db.execute('''
                SELECT * FROM auto_broadcasts 
                ORDER BY created_at DESC
            ''') as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]


async def get_auto_broadcast(auto_id: int) -> Optional[Dict]:
    """Получить конкретную автоматическую рассылку"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('''
            SELECT * FROM auto_broadcasts WHERE id = ?
        ''', (auto_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def toggle_auto_broadcast(auto_id: int) -> bool:
    """Переключить активность автоматической рассылки"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        # Получаем текущее состояние
        async with db.execute('''
            SELECT is_active FROM auto_broadcasts WHERE id = ?
        ''', (auto_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return False

            new_status = 0 if row[0] else 1

        await db.execute('''
            UPDATE auto_broadcasts SET is_active = ? WHERE id = ?
        ''', (new_status, auto_id))
        await db.commit()
        return True


async def delete_auto_broadcast(auto_id: int) -> bool:
    """Удалить автоматическую рассылку"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        # Сначала удаляем записи об отправках
        await db.execute('''
            DELETE FROM auto_broadcast_sent WHERE auto_broadcast_id = ?
        ''', (auto_id,))

        cursor = await db.execute('''
            DELETE FROM auto_broadcasts WHERE id = ?
        ''', (auto_id,))
        await db.commit()
        return cursor.rowcount > 0


async def increment_auto_broadcast_sent(auto_id: int) -> None:
    """Увеличить счётчик отправок автоматической рассылки"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute('''
            UPDATE auto_broadcasts SET sent_count = sent_count + 1 WHERE id = ?
        ''', (auto_id,))
        await db.commit()


async def mark_auto_broadcast_sent(auto_id: int, user_id: int) -> bool:
    """Отметить, что автоматическая рассылка отправлена пользователю"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        try:
            await db.execute('''
                INSERT INTO auto_broadcast_sent (auto_broadcast_id, user_id)
                VALUES (?, ?)
            ''', (auto_id, user_id))
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            # Уже отправлено этому пользователю
            return False


async def is_auto_broadcast_sent(auto_id: int, user_id: int) -> bool:
    """Проверить, была ли авто-рассылка уже отправлена пользователю"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute('''
            SELECT 1 FROM auto_broadcast_sent 
            WHERE auto_broadcast_id = ? AND user_id = ?
        ''', (auto_id, user_id)) as cursor:
            return await cursor.fetchone() is not None


async def get_auto_broadcast_eligible_users(trigger_type: str, delay_hours: int) -> List[Dict]:
    """
    Получить пользователей, подходящих для автоматической рассылки

    trigger_type:
    - 'only_start': только нажали /start, прошло delay_hours часов
    - 'no_payment': нажали оплатить, но не оплатили, прошло delay_hours часов
    - 'rejected': отклонённая оплата, прошло delay_hours часов
    - 'no_screenshot': нажали оплатить без скрина, прошло delay_hours часов
    """
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row

        threshold_time = datetime.now() - timedelta(hours=delay_hours)
        threshold_str = threshold_time.strftime('%Y-%m-%d %H:%M:%S')

        if trigger_type == 'only_start':
            # Пользователи, которые только нажали /start и больше ничего не делали
            async with db.execute('''
                SELECT u.user_id, u.username, u.first_name
                FROM users u
                WHERE u.has_paid = 0
                AND u.created_at <= ?
                AND NOT EXISTS (
                    SELECT 1 FROM user_events e 
                    WHERE e.user_id = u.user_id 
                    AND e.event_type IN (?, ?, ?)
                )
            ''', (threshold_str, EventType.PAYMENT_BUTTON_CLICKED, EventType.SCREENSHOT_SENT, EventType.CALCULATOR_STARTED)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

        elif trigger_type == 'no_payment':
            # Пользователи, которые нажали оплатить, но не оплатили
            async with db.execute('''
                SELECT DISTINCT u.user_id, u.username, u.first_name
                FROM users u
                JOIN user_events e ON u.user_id = e.user_id
                WHERE e.event_type = ?
                AND e.created_at <= ?
                AND u.has_paid = 0
            ''', (EventType.PAYMENT_BUTTON_CLICKED, threshold_str)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

        elif trigger_type == 'rejected':
            # Пользователи с отклонёнными запросами
            async with db.execute('''
                SELECT DISTINCT u.user_id, u.username, u.first_name
                FROM users u
                JOIN payment_requests pr ON u.user_id = pr.user_id
                WHERE pr.status = 'rejected'
                AND pr.created_at <= ?
                AND u.has_paid = 0
            ''', (threshold_str,)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

        elif trigger_type == 'no_screenshot':
            # Пользователи, которые нажали "Я оплатил(а)" но не прислали скрин
            async with db.execute('''
                SELECT DISTINCT u.user_id, u.username, u.first_name
                FROM users u
                JOIN user_events e ON u.user_id = e.user_id
                WHERE e.event_type = ?
                AND e.created_at <= ?
                AND u.has_paid = 0
                AND NOT EXISTS (
                    SELECT 1 FROM user_events e2
                    WHERE e2.user_id = u.user_id
                    AND e2.event_type = ?
                )
            ''', (EventType.PAYMENT_BUTTON_CLICKED, threshold_str, EventType.SCREENSHOT_SENT)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

        return []


# ==================== Broadcast Chain Management ====================

async def init_chain_tables():
    """Инициализация таблиц для цепочек рассылок"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        # Таблица цепочек рассылок (воронок)
        await db.execute('''
            CREATE TABLE IF NOT EXISTS broadcast_chains (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                trigger_type TEXT NOT NULL CHECK(trigger_type IN ('manual', 'subscription_end', 'payment_approved', 'custom')),
                is_active INTEGER DEFAULT 1,
                created_by INTEGER NOT NULL,
                created_by_username TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Таблица шагов цепочки
        await db.execute('''
            CREATE TABLE IF NOT EXISTS chain_steps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chain_id INTEGER NOT NULL,
                step_order INTEGER NOT NULL,
                content TEXT NOT NULL,
                media_type TEXT CHECK(media_type IN ('photo', 'video', NULL)),
                media_file_id TEXT,
                delay_hours INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(chain_id) REFERENCES broadcast_chains(id) ON DELETE CASCADE,
                UNIQUE(chain_id, step_order)
            )
        ''')

        # Таблица кнопок шага (с действиями)
        await db.execute('''
            CREATE TABLE IF NOT EXISTS chain_step_buttons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                step_id INTEGER NOT NULL,
                button_text TEXT NOT NULL,
                button_order INTEGER NOT NULL,
                action_type TEXT NOT NULL CHECK(action_type IN ('next_step', 'goto_step', 'url', 'command', 'stop_chain', 'payment_main', 'payment_fmd', 'payment_bundle')),
                action_value TEXT,
                next_step_id INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(step_id) REFERENCES chain_steps(id) ON DELETE CASCADE,
                FOREIGN KEY(next_step_id) REFERENCES chain_steps(id) ON DELETE SET NULL
            )
        ''')

        # Таблица состояния пользователя в цепочке
        await db.execute('''
            CREATE TABLE IF NOT EXISTS chain_user_state (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                chain_id INTEGER NOT NULL,
                current_step_id INTEGER NOT NULL,
                status TEXT CHECK(status IN ('active', 'completed', 'stopped')) DEFAULT 'active',
                started_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_action_at TEXT,
                next_message_at TEXT,
                FOREIGN KEY(user_id) REFERENCES users(user_id),
                FOREIGN KEY(chain_id) REFERENCES broadcast_chains(id) ON DELETE CASCADE,
                FOREIGN KEY(current_step_id) REFERENCES chain_steps(id),
                UNIQUE(user_id, chain_id)
            )
        ''')

        # Таблица истории отправок цепочки
        await db.execute('''
            CREATE TABLE IF NOT EXISTS chain_message_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                chain_id INTEGER NOT NULL,
                step_id INTEGER NOT NULL,
                button_clicked TEXT,
                sent_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(user_id),
                FOREIGN KEY(chain_id) REFERENCES broadcast_chains(id) ON DELETE CASCADE,
                FOREIGN KEY(step_id) REFERENCES chain_steps(id) ON DELETE CASCADE
            )
        ''')

        # Индексы
        await db.execute('''
            CREATE INDEX IF NOT EXISTS idx_chain_user_state_active 
            ON chain_user_state(status, next_message_at)
        ''')

        await db.execute('''
            CREATE INDEX IF NOT EXISTS idx_chain_steps_order 
            ON chain_steps(chain_id, step_order)
        ''')

        await db.commit()


async def create_chain(
    name: str,
    trigger_type: str,
    created_by: int,
    created_by_username: str = None,
    description: str = None
) -> int:
    """Создать новую цепочку рассылок"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        cursor = await db.execute('''
            INSERT INTO broadcast_chains (name, description, trigger_type, created_by, created_by_username)
            VALUES (?, ?, ?, ?, ?)
        ''', (name, description, trigger_type, created_by, created_by_username))
        await db.commit()
        return cursor.lastrowid


async def get_chain(chain_id: int) -> Optional[Dict]:
    """Получить цепочку по ID"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('''
            SELECT * FROM broadcast_chains WHERE id = ?
        ''', (chain_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def get_all_chains(active_only: bool = False) -> List[Dict]:
    """Получить все цепочки"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row
        if active_only:
            async with db.execute('''
                SELECT * FROM broadcast_chains WHERE is_active = 1 ORDER BY created_at DESC
            ''') as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
        else:
            async with db.execute('''
                SELECT * FROM broadcast_chains ORDER BY created_at DESC
            ''') as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]


async def update_chain(chain_id: int, **kwargs) -> bool:
    """Обновить цепочку"""
    allowed_fields = ['name', 'description', 'trigger_type', 'is_active']
    fields = {k: v for k, v in kwargs.items() if k in allowed_fields}

    if not fields:
        return False

    set_clause = ', '.join([f"{k} = ?" for k in fields.keys()])
    values = list(fields.values()) + [chain_id]

    async with aiosqlite.connect(DATABASE_NAME) as db:
        cursor = await db.execute(f'''
            UPDATE broadcast_chains SET {set_clause} WHERE id = ?
        ''', values)
        await db.commit()
        return cursor.rowcount > 0


async def delete_chain(chain_id: int) -> bool:
    """Удалить цепочку (каскадно удалит все шаги и состояния)"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        cursor = await db.execute('''
            DELETE FROM broadcast_chains WHERE id = ?
        ''', (chain_id,))
        await db.commit()
        return cursor.rowcount > 0


async def toggle_chain_active(chain_id: int) -> bool:
    """Переключить активность цепочки"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute('''
            SELECT is_active FROM broadcast_chains WHERE id = ?
        ''', (chain_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return False
            new_status = 0 if row[0] else 1

        await db.execute('''
            UPDATE broadcast_chains SET is_active = ? WHERE id = ?
        ''', (new_status, chain_id))
        await db.commit()
        return True


# ==================== Chain Steps ====================

async def add_chain_step(
    chain_id: int,
    step_order: int,
    content: str,
    media_type: str = None,
    media_file_id: str = None,
    delay_hours: int = 0
) -> int:
    """Добавить шаг в цепочку"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        cursor = await db.execute('''
            INSERT INTO chain_steps (chain_id, step_order, content, media_type, media_file_id, delay_hours)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (chain_id, step_order, content, media_type, media_file_id, delay_hours))
        await db.commit()
        return cursor.lastrowid


async def get_chain_step(step_id: int) -> Optional[Dict]:
    """Получить шаг по ID"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('''
            SELECT * FROM chain_steps WHERE id = ?
        ''', (step_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def get_chain_steps(chain_id: int) -> List[Dict]:
    """Получить все шаги цепочки в порядке"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('''
            SELECT * FROM chain_steps WHERE chain_id = ? ORDER BY step_order ASC
        ''', (chain_id,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def get_first_chain_step(chain_id: int) -> Optional[Dict]:
    """Получить первый шаг цепочки"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('''
            SELECT * FROM chain_steps WHERE chain_id = ? ORDER BY step_order ASC LIMIT 1
        ''', (chain_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def get_next_chain_step(chain_id: int, current_order: int) -> Optional[Dict]:
    """Получить следующий шаг цепочки"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('''
            SELECT * FROM chain_steps 
            WHERE chain_id = ? AND step_order > ?
            ORDER BY step_order ASC LIMIT 1
        ''', (chain_id, current_order)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def update_chain_step(step_id: int, **kwargs) -> bool:
    """Обновить шаг цепочки"""
    allowed_fields = ['content', 'media_type',
                      'media_file_id', 'delay_hours', 'step_order']
    fields = {k: v for k, v in kwargs.items() if k in allowed_fields}

    if not fields:
        return False

    set_clause = ', '.join([f"{k} = ?" for k in fields.keys()])
    values = list(fields.values()) + [step_id]

    async with aiosqlite.connect(DATABASE_NAME) as db:
        cursor = await db.execute(f'''
            UPDATE chain_steps SET {set_clause} WHERE id = ?
        ''', values)
        await db.commit()
        return cursor.rowcount > 0


async def delete_chain_step(step_id: int) -> bool:
    """Удалить шаг цепочки"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        cursor = await db.execute('''
            DELETE FROM chain_steps WHERE id = ?
        ''', (step_id,))
        await db.commit()
        return cursor.rowcount > 0


async def get_chain_steps_count(chain_id: int) -> int:
    """Получить количество шагов в цепочке"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute('''
            SELECT COUNT(*) FROM chain_steps WHERE chain_id = ?
        ''', (chain_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


# ==================== Chain Step Buttons ====================

async def add_step_button(
    step_id: int,
    button_text: str,
    button_order: int,
    action_type: str,
    action_value: str = None,
    next_step_id: int = None
) -> int:
    """Добавить кнопку к шагу"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        cursor = await db.execute('''
            INSERT INTO chain_step_buttons (step_id, button_text, button_order, action_type, action_value, next_step_id)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (step_id, button_text, button_order, action_type, action_value, next_step_id))
        await db.commit()
        return cursor.lastrowid


async def get_step_buttons(step_id: int) -> List[Dict]:
    """Получить все кнопки шага"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('''
            SELECT * FROM chain_step_buttons WHERE step_id = ? ORDER BY button_order ASC
        ''', (step_id,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def get_step_button(button_id: int) -> Optional[Dict]:
    """Получить кнопку по ID"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('''
            SELECT * FROM chain_step_buttons WHERE id = ?
        ''', (button_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def delete_step_button(button_id: int) -> bool:
    """Удалить кнопку шага"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        cursor = await db.execute('''
            DELETE FROM chain_step_buttons WHERE id = ?
        ''', (button_id,))
        await db.commit()
        return cursor.rowcount > 0


async def delete_step_buttons(step_id: int) -> int:
    """Удалить все кнопки шага"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        cursor = await db.execute('''
            DELETE FROM chain_step_buttons WHERE step_id = ?
        ''', (step_id,))
        await db.commit()
        return cursor.rowcount


# ==================== Chain User State ====================

async def start_chain_for_user(user_id: int, chain_id: int, first_step_id: int) -> int:
    """Запустить цепочку для пользователя"""
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DATABASE_NAME) as db:
        # Проверяем, есть ли уже запись для этого пользователя и цепочки
        async with db.execute('''
            SELECT id, status FROM chain_user_state WHERE user_id = ? AND chain_id = ?
        ''', (user_id, chain_id)) as cursor:
            existing = await cursor.fetchone()
            if existing:
                state_id, status = existing
                if status == 'active':
                    # Уже активна - возвращаем существующий ID
                    return state_id
                else:
                    # Перезапускаем цепочку - обновляем запись
                    await db.execute('''
                        UPDATE chain_user_state 
                        SET current_step_id = ?, status = 'active', started_at = ?, last_action_at = ?, next_message_at = ?
                        WHERE id = ?
                    ''', (first_step_id, now, now, now, state_id))
                    await db.commit()
                    return state_id

        # Создаём новую запись
        cursor = await db.execute('''
            INSERT INTO chain_user_state (user_id, chain_id, current_step_id, status, started_at, last_action_at, next_message_at)
            VALUES (?, ?, ?, 'active', ?, ?, ?)
        ''', (user_id, chain_id, first_step_id, now, now, now))
        await db.commit()
        return cursor.lastrowid


async def get_user_chain_state(user_id: int, chain_id: int) -> Optional[Dict]:
    """Получить состояние пользователя в цепочке"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('''
            SELECT * FROM chain_user_state WHERE user_id = ? AND chain_id = ?
        ''', (user_id, chain_id)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def get_user_active_chains(user_id: int) -> List[Dict]:
    """Получить все активные цепочки пользователя"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('''
            SELECT cus.*, bc.name as chain_name 
            FROM chain_user_state cus
            JOIN broadcast_chains bc ON cus.chain_id = bc.id
            WHERE cus.user_id = ? AND cus.status = 'active'
        ''', (user_id,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def update_user_chain_state(
    user_id: int,
    chain_id: int,
    current_step_id: int = None,
    status: str = None,
    next_message_at: datetime = None
) -> bool:
    """Обновить состояние пользователя в цепочке"""
    updates = []
    values = []

    if current_step_id is not None:
        updates.append("current_step_id = ?")
        values.append(current_step_id)

    if status is not None:
        updates.append("status = ?")
        values.append(status)

    if next_message_at is not None:
        updates.append("next_message_at = ?")
        values.append(next_message_at.isoformat())

    updates.append("last_action_at = ?")
    values.append(datetime.now().isoformat())

    if not updates:
        return False

    values.extend([user_id, chain_id])

    async with aiosqlite.connect(DATABASE_NAME) as db:
        cursor = await db.execute(f'''
            UPDATE chain_user_state SET {', '.join(updates)} WHERE user_id = ? AND chain_id = ?
        ''', values)
        await db.commit()
        return cursor.rowcount > 0


async def stop_user_chain(user_id: int, chain_id: int) -> bool:
    """Остановить цепочку для пользователя"""
    return await update_user_chain_state(user_id, chain_id, status='stopped')


async def complete_user_chain(user_id: int, chain_id: int) -> bool:
    """Пометить цепочку как завершённую"""
    return await update_user_chain_state(user_id, chain_id, status='completed')


async def get_pending_chain_messages() -> List[Dict]:
    """Получить все pending сообщения цепочки которые пора отправить"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row
        now = datetime.now().isoformat()
        async with db.execute('''
            SELECT cus.*, cs.content, cs.media_type, cs.media_file_id, cs.step_order,
                   bc.name as chain_name, u.username, u.first_name
            FROM chain_user_state cus
            JOIN chain_steps cs ON cus.current_step_id = cs.id
            JOIN broadcast_chains bc ON cus.chain_id = bc.id
            JOIN users u ON cus.user_id = u.user_id
            WHERE cus.status = 'active'
            AND cus.next_message_at <= ?
            AND bc.is_active = 1
        ''', (now,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def log_chain_message(user_id: int, chain_id: int, step_id: int, button_clicked: str = None):
    """Записать историю отправки сообщения цепочки"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute('''
            INSERT INTO chain_message_history (user_id, chain_id, step_id, button_clicked)
            VALUES (?, ?, ?, ?)
        ''', (user_id, chain_id, step_id, button_clicked))
        await db.commit()


# ==================== User Management ====================

async def get_all_users() -> List[Dict]:
    """Получить всех пользователей"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('''
            SELECT user_id, username, first_name, has_paid, has_paid_fmd, has_paid_bundle, has_paid_dry, created_at
            FROM users
            ORDER BY created_at DESC
        ''') as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def get_users_by_payment_filter(filter_type: str) -> List[Dict]:
    """
    Получить пользователей по фильтру оплаты

    filter_type:
    - 'all': все пользователи
    - 'paid_main': оплатившие основной рацион
    - 'paid_fmd': оплатившие FMD протокол
    - 'paid_bundle': оплатившие комплект
    - 'paid_dry': оплатившие Сушку
    """
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row

        if filter_type == 'paid_main':
            async with db.execute('''
                SELECT user_id, username, first_name, has_paid, has_paid_fmd, has_paid_bundle, has_paid_dry, created_at
                FROM users
                WHERE has_paid = 1
                ORDER BY created_at DESC
            ''') as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

        elif filter_type == 'paid_fmd':
            async with db.execute('''
                SELECT user_id, username, first_name, has_paid, has_paid_fmd, has_paid_bundle, has_paid_dry, created_at
                FROM users
                WHERE has_paid_fmd = 1
                ORDER BY created_at DESC
            ''') as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

        elif filter_type == 'paid_bundle':
            async with db.execute('''
                SELECT user_id, username, first_name, has_paid, has_paid_fmd, has_paid_bundle, has_paid_dry, created_at
                FROM users
                WHERE has_paid_bundle = 1
                ORDER BY created_at DESC
            ''') as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

        elif filter_type == 'paid_dry':
            async with db.execute('''
                SELECT user_id, username, first_name, has_paid, has_paid_fmd, has_paid_bundle, has_paid_dry, created_at
                FROM users
                WHERE has_paid_dry = 1
                ORDER BY created_at DESC
            ''') as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

        else:  # 'all'
            return await get_all_users()


async def reset_user_payment(user_id: int, payment_type: str) -> bool:
    """
    Сбросить оплату пользователя

    payment_type:
    - 'main': сбросить оплату основного рациона
    - 'fmd': сбросить оплату FMD протокола
    - 'bundle': сбросить оплату комплекта
    - 'dry': сбросить оплату Сушки
    - 'all': сбросить все оплаты
    """
    async with aiosqlite.connect(DATABASE_NAME) as db:
        if payment_type == 'main':
            cursor = await db.execute('''
                UPDATE users SET has_paid = 0 WHERE user_id = ?
            ''', (user_id,))
        elif payment_type == 'fmd':
            cursor = await db.execute('''
                UPDATE users SET has_paid_fmd = 0 WHERE user_id = ?
            ''', (user_id,))
        elif payment_type == 'bundle':
            cursor = await db.execute('''
                UPDATE users SET has_paid_bundle = 0 WHERE user_id = ?
            ''', (user_id,))
        elif payment_type == 'dry':
            cursor = await db.execute('''
                UPDATE users SET has_paid_dry = 0 WHERE user_id = ?
            ''', (user_id,))
        elif payment_type == 'all':
            cursor = await db.execute('''
                UPDATE users SET has_paid = 0, has_paid_fmd = 0, has_paid_bundle = 0, has_paid_dry = 0 WHERE user_id = ?
            ''', (user_id,))
        else:
            return False

        await db.commit()
        return cursor.rowcount > 0


async def search_user_by_username_or_id(query: str) -> List[Dict]:
    """Поиск пользователя по username или user_id"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row

        # Попытка поиска по user_id (если запрос — число)
        try:
            user_id = int(query)
            async with db.execute('''
                SELECT user_id, username, first_name, has_paid, has_paid_fmd, has_paid_bundle, has_paid_dry, created_at
                FROM users
                WHERE user_id = ?
            ''', (user_id,)) as cursor:
                rows = await cursor.fetchall()
                if rows:
                    return [dict(row) for row in rows]
        except ValueError:
            pass

        # Поиск по username (без @)
        search_query = query.lstrip('@').lower()
        async with db.execute('''
            SELECT user_id, username, first_name, has_paid, has_paid_fmd, has_paid_bundle, has_paid_dry, created_at
            FROM users
            WHERE LOWER(username) LIKE ? OR LOWER(first_name) LIKE ?
            ORDER BY created_at DESC
            LIMIT 50
        ''', (f'%{search_query}%', f'%{search_query}%')) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def get_chain_stats(chain_id: int) -> Dict:
    """Получить статистику цепочки"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        stats = {}

        # Всего пользователей запустили цепочку
        async with db.execute('''
            SELECT COUNT(DISTINCT user_id) FROM chain_user_state WHERE chain_id = ?
        ''', (chain_id,)) as cursor:
            row = await cursor.fetchone()
            stats['total_started'] = row[0] if row else 0

        # Активных
        async with db.execute('''
            SELECT COUNT(*) FROM chain_user_state WHERE chain_id = ? AND status = 'active'
        ''', (chain_id,)) as cursor:
            row = await cursor.fetchone()
            stats['active'] = row[0] if row else 0

        # Завершили
        async with db.execute('''
            SELECT COUNT(*) FROM chain_user_state WHERE chain_id = ? AND status = 'completed'
        ''', (chain_id,)) as cursor:
            row = await cursor.fetchone()
            stats['completed'] = row[0] if row else 0

        # Остановили
        async with db.execute('''
            SELECT COUNT(*) FROM chain_user_state WHERE chain_id = ? AND status = 'stopped'
        ''', (chain_id,)) as cursor:
            row = await cursor.fetchone()
            stats['stopped'] = row[0] if row else 0

        # Всего отправлено сообщений
        async with db.execute('''
            SELECT COUNT(*) FROM chain_message_history WHERE chain_id = ?
        ''', (chain_id,)) as cursor:
            row = await cursor.fetchone()
            stats['messages_sent'] = row[0] if row else 0

        return stats
