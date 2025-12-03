import aiosqlite
from datetime import datetime
from typing import Optional

DATABASE_NAME = 'bot_database.db'


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
