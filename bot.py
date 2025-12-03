import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
import database as db
from handlers import user_router, admin_router, calculator_router


# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('bot.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


async def on_startup(bot: Bot):
    """Действия при запуске бота"""
    await db.init_db()
    logger.info("Database initialized")

    bot_info = await bot.get_me()
    logger.info(f"Bot started: @{bot_info.username}")


async def on_shutdown(bot: Bot):
    """Действия при остановке бота"""
    logger.info("Bot is shutting down...")


async def main():
    """Главная функция запуска бота"""
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is not set! Check your .env file")
        sys.exit(1)

    # Инициализация бота с настройками по умолчанию
    # protect_content=True запрещает пересылку и копирование сообщений
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML,
            protect_content=True
        )
    )

    # Инициализация диспетчера с FSM storage для админки
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Регистрация роутеров
    dp.include_router(user_router)
    dp.include_router(admin_router)
    dp.include_router(calculator_router)

    # Регистрация событий startup/shutdown
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    logger.info("Starting bot...")

    try:
        # Удаляем вебхук (на случай если был) и пропускаем накопившиеся апдейты
        await bot.delete_webhook(drop_pending_updates=True)
        # Запуск polling
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise
