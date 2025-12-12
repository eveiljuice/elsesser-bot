import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from apscheduler import AsyncScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from config import BOT_TOKEN, ADMIN_CHANNEL_ID
import database as db
from handlers import user_router, admin_router, calculator_router
from followup import process_pending_followups, schedule_new_followups


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

# Глобальные переменные
scheduler: AsyncScheduler = None
bot_instance: Bot = None


# ==================== Scheduler Tasks ====================
# APScheduler требует обычные функции (не lambda)

async def task_process_followups():
    """Задача: отправка запланированных follow-up сообщений"""
    try:
        if bot_instance:
            await process_pending_followups(bot_instance)
    except Exception as e:
        logger.error(f"Error in task_process_followups: {e}")


async def task_schedule_followups():
    """Задача: поиск новых пользователей для follow-up"""
    try:
        if bot_instance:
            await schedule_new_followups(bot_instance)
    except Exception as e:
        logger.error(f"Error in task_schedule_followups: {e}")


async def task_send_weekly_report():
    """
    Задача: отправка детального недельного отчёта в админ-чат.
    Запускается каждое воскресенье в 20:00.
    """
    if not bot_instance or not ADMIN_CHANNEL_ID:
        return

    try:
        report = await db.get_weekly_report()

        # Рассчитываем конверсии за неделю
        started = report['started_week'] or 1
        clicked = report['clicked_payment_week'] or 1

        conv_start_to_click = (
            report['clicked_payment_week'] / started * 100) if started else 0
        conv_click_to_screen = (
            report['screenshot_week'] / clicked * 100) if clicked else 0
        conv_start_to_paid = (
            report['paid_week'] / started * 100) if started else 0

        # Follow-up конверсия
        followup_sent = report['followup_sent_week'] or 1
        followup_conv = (report['paid_after_followup_week'] /
                         followup_sent * 100) if followup_sent else 0

        # Формируем строку с топ днями
        weekday_stats = report.get('payments_by_weekday', {})
        if weekday_stats:
            weekday_str = " | ".join(
                [f"{day}: {cnt}" for day, cnt in weekday_stats.items()])
        else:
            weekday_str = "Нет данных"

        # Формируем сообщение
        message_text = (
            "📊 <b>НЕДЕЛЬНЫЙ ОТЧЁТ</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━\n\n"

            "📈 <b>Общая статистика:</b>\n"
            f"├ 👥 Всего пользователей: <b>{report['total_users']}</b>\n"
            f"└ 💰 Всего оплатили: <b>{report['total_paid']}</b>\n\n"

            "📅 <b>За эту неделю:</b>\n"
            f"├ 🆕 Новых пользователей: <b>{report['new_users_week']}</b>\n"
            f"├ 💳 Оплатили: <b>{report['paid_week']}</b>\n"
            f"├ ✅ Одобрено запросов: {report['approved_week']}\n"
            f"├ ❌ Отклонено запросов: {report['rejected_week']}\n"
            f"└ ⏳ Ожидают проверки: {report['pending_now']}\n\n"

            "📊 <b>Воронка за неделю:</b>\n"
            f"├ /start: <b>{report['started_week']}</b>\n"
            f"├ → Нажали «Оплатила»: {report['clicked_payment_week']} ({conv_start_to_click:.1f}%)\n"
            f"├ → Прислали скрин: {report['screenshot_week']} ({conv_click_to_screen:.1f}%)\n"
            f"└ → Оплатили: {report['paid_week']} ({conv_start_to_paid:.1f}%)\n\n"

            "📬 <b>Follow-up за неделю:</b>\n"
            f"├ 📤 Отправлено: {report['followup_sent_week']}\n"
            f"└ ✅ Оплатили после: {report['paid_after_followup_week']} ({followup_conv:.1f}%)\n\n"

            "🔍 <b>Потерянные клиенты (всего):</b>\n"
            f"├ 😴 Только /start: {report['only_start_total']}\n"
            f"└ 🤔 Нажали оплату без скрина: {report['clicked_no_screenshot_total']}\n\n"

            "📊 <b>Калькулятор за неделю:</b>\n"
            f"└ Прошли: {report['calculator_completed_week']}\n\n"

            f"📅 <b>Оплаты по дням:</b> {weekday_str}\n\n"

            "━━━━━━━━━━━━━━━━━━━━━━━\n"
            "🤖 <i>Отчёт сформирован автоматически</i>"
        )

        await bot_instance.send_message(
            chat_id=ADMIN_CHANNEL_ID,
            text=message_text,
            parse_mode="HTML"
        )
        logger.info("Weekly report sent successfully")

    except Exception as e:
        logger.error(f"Failed to send weekly report: {e}")


async def on_startup(bot: Bot):
    """Действия при запуске бота"""
    # БД уже инициализирована в main(), но вызываем снова на всякий случай
    # (CREATE TABLE IF NOT EXISTS безопасен)
    await db.init_db()

    bot_info = await bot.get_me()
    logger.info(f"Bot started: @{bot_info.username}")
    logger.info("Follow-up scheduler is running")


async def on_shutdown(bot: Bot):
    """Действия при остановке бота"""
    logger.info("Bot is shutting down...")


async def main():
    """Главная функция запуска бота"""
    global scheduler, bot_instance

    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is not set! Check your .env file")
        sys.exit(1)

    # Инициализация бота с настройками по умолчанию
    # protect_content=True запрещает пересылку и копирование сообщений
    bot_instance = Bot(
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
        # Инициализируем БД ДО запуска scheduler (чтобы таблицы существовали)
        await db.init_db()
        logger.info("Database initialized")

        # Удаляем вебхук (на случай если был) и пропускаем накопившиеся апдейты
        await bot_instance.delete_webhook(drop_pending_updates=True)

        # ==================== Scheduler для follow-up сообщений ====================
        async with AsyncScheduler() as scheduler:
            # Задача 1: Отправка запланированных follow-up сообщений (каждые 5 минут)
            await scheduler.add_schedule(
                task_process_followups,
                IntervalTrigger(minutes=5),
                id="process_followups"
            )

            # Задача 2: Поиск новых пользователей для follow-up (каждый час)
            await scheduler.add_schedule(
                task_schedule_followups,
                IntervalTrigger(hours=1),
                id="schedule_followups"
            )

            # Задача 3: Недельный отчёт каждое воскресенье в 20:00
            await scheduler.add_schedule(
                task_send_weekly_report,
                CronTrigger(day_of_week="sun", hour=20, minute=0),
                id="weekly_report"
            )

            # Запускаем scheduler в фоне
            await scheduler.start_in_background()
            logger.info("Follow-up scheduler started")

            # Запуск polling
            await dp.start_polling(bot_instance)
    finally:
        await bot_instance.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise
