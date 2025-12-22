"""
Follow-up (триггерные) сообщения и рассылки для возврата пользователей
"""
import logging
import random
import asyncio
from datetime import datetime, timedelta
from typing import Optional

from aiogram import Bot
from aiogram.enums import ParseMode

import database as db
from config import PAYMENT_AMOUNT

logger = logging.getLogger(__name__)


# ==================== Broadcast System ====================

async def send_broadcast_message(bot: Bot, user_id: int, content: str) -> bool:
    """
    Отправить сообщение рассылки пользователю
    
    Returns: True если успешно, False если ошибка
    """
    try:
        await bot.send_message(
            chat_id=user_id,
            text=content,
            parse_mode=ParseMode.HTML
        )
        return True
    except Exception as e:
        logger.error(f"Failed to send broadcast to user {user_id}: {e}")
        return False


async def process_pending_broadcasts(bot: Bot):
    """
    Обработать все pending рассылки, которые пора отправить
    Вызывается периодически из scheduler
    """
    broadcasts = await db.get_pending_broadcasts()
    
    for broadcast in broadcasts:
        broadcast_id = broadcast['id']
        audience = broadcast['audience']
        content = broadcast['content']
        
        logger.info(f"Starting broadcast {broadcast_id} to audience '{audience}'")
        
        # Помечаем как sending
        await db.update_broadcast_status(broadcast_id, 'sending')
        
        # Получаем пользователей
        users = await db.get_broadcast_audience_users(audience)
        
        sent_count = 0
        failed_count = 0
        
        for user in users:
            user_id = user['user_id']
            success = await send_broadcast_message(bot, user_id, content)
            
            if success:
                sent_count += 1
            else:
                failed_count += 1
            
            # Небольшая задержка чтобы не флудить API
            await asyncio.sleep(0.05)
        
        # Обновляем статус
        await db.update_broadcast_status(broadcast_id, 'sent', sent_count, failed_count)
        logger.info(f"Broadcast {broadcast_id} completed: sent={sent_count}, failed={failed_count}")


# ==================== Шаблоны сообщений ====================

# Сообщения для тех, кто только нажал /start и ничего не делал
ONLY_START_MESSAGES = [
    (
        "👋 Привет!\n\n"
        "Вчера ты заходила посмотреть рационы питания, но так и не продолжил(а).\n\n"
        "🍽 У нас есть <b>готовые рационы</b> с КБЖУ на разную калорийность — "
        "от похудения до набора массы.\n\n"
        "💡 <i>Не нужно считать калории — всё уже рассчитано!</i>\n\n"
        f"Доступ всего <b>{PAYMENT_AMOUNT} ₽</b>. Напиши /start, чтобы начать!"
    ),
    (
        "🤔 Эй, ты вчера интересовалась рационами питания...\n\n"
        "Знаю, бывает сложно решиться. Но представь:\n"
        "✅ Не нужно думать, что готовить\n"
        "✅ Не нужно считать калории\n"
        "✅ Всё расписано по дням\n\n"
        "🎯 Просто следуй рациону и получай результат!\n\n"
        f"Цена вопроса — <b>{PAYMENT_AMOUNT} ₽</b> за полный доступ.\n"
        "Жми /start и погнали! 💪"
    ),
    (
        "🔥 Напоминание для тебя!\n\n"
        "Вчера ты начала знакомство с ботом рационов.\n"
        "У меня есть <b>готовые планы питания</b> на любую цель:\n\n"
        "• 🏃 Похудение (от 1200 ккал)\n"
        "• ⚖️ Поддержание формы\n"
        "• 💪 Набор массы (до 2100 ккал)\n\n"
        "Каждый день расписан: завтрак, обед, ужин с рецептами.\n\n"
        f"Всего <b>{PAYMENT_AMOUNT} ₽</b> — и доступ твой навсегда! 🚀"
    ),
]

# Сообщения для тех, кто нажал "Я оплатил(а)", но не прислал скрин
CLICKED_PAYMENT_MESSAGES = [
    (
        "⏳ Привет! Ты нажала кнопку «Я оплатила», "
        "но мы не получили скриншот оплаты.\n\n"
        "📸 <b>Чтобы получить доступ:</b>\n"
        "1. Оплати по реквизитам\n"
        "2. Сделай скриншот\n"
        "3. Отправь его мне\n\n"
        "Если возникли вопросы — напиши, поможем! 💬"
    ),
    (
        "👀 Заметили, что ты была близко к получению доступа!\n\n"
        "Ты нажала «Я оплатила», но скриншот так и не пришёл.\n\n"
        "🤷 Может, что-то пошло не так?\n"
        "• Не получилось оплатить?\n"
        "• Забыла отправить скрин?\n\n"
        "Напиши /start и попробуй ещё раз. Мы рядом! 🙌"
    ),
    (
        "🔔 Напоминание!\n\n"
        "Пару часов назад ты хотела подтвердить оплату, "
        "но мы так и не получили скриншот.\n\n"
        "Если уже оплатила — просто пришли фото/скрин чека.\n"
        "Если ещё нет — не проблема, реквизиты по команде /start.\n\n"
        "Ждём тебя! 🎯"
    ),
]


def get_random_message(message_type: str) -> str:
    """Получить случайное сообщение нужного типа"""
    if message_type == 'only_start':
        return random.choice(ONLY_START_MESSAGES)
    elif message_type == 'clicked_payment':
        return random.choice(CLICKED_PAYMENT_MESSAGES)
    return ""


async def send_followup_message(bot: Bot, user_id: int, message_type: str) -> bool:
    """
    Отправить follow-up сообщение пользователю
    
    Returns: True если успешно, False если ошибка
    """
    message = get_random_message(message_type)
    if not message:
        return False
    
    try:
        await bot.send_message(
            chat_id=user_id,
            text=message,
            parse_mode=ParseMode.HTML
        )
        logger.info(f"Follow-up '{message_type}' sent to user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to send follow-up to user {user_id}: {e}")
        return False


async def process_pending_followups(bot: Bot):
    """
    Обработать все pending follow-up сообщения
    Вызывается периодически из scheduler
    """
    followups = await db.get_pending_followups()
    
    for followup in followups:
        # Пропускаем если пользователь уже оплатил
        if followup['has_paid']:
            await db.mark_followup_sent(followup['id'], 'cancelled')
            continue
        
        # Отправляем сообщение
        success = await send_followup_message(
            bot,
            followup['user_id'],
            followup['message_type']
        )
        
        # Обновляем статус
        status = 'sent' if success else 'failed'
        await db.mark_followup_sent(followup['id'], status)


async def schedule_new_followups(bot: Bot):
    """
    Найти пользователей для follow-up и запланировать им сообщения
    Вызывается периодически из scheduler
    """
    # 1. Пользователи, которые только нажали /start 24+ часов назад
    only_start_users = await db.get_users_for_followup('only_start')
    for user in only_start_users:
        # Планируем отправку через 1-3 часа (рандомно, чтобы не было массовой рассылки)
        delay_hours = random.uniform(1, 3)
        scheduled_at = datetime.now() + timedelta(hours=delay_hours)
        await db.schedule_followup(user['user_id'], 'only_start', scheduled_at)
        logger.info(f"Scheduled 'only_start' followup for user {user['user_id']} at {scheduled_at}")
    
    # 2. Пользователи, которые нажали "Я оплатил(а)" 2+ часа назад без скрина
    clicked_users = await db.get_users_for_followup('clicked_payment')
    for user in clicked_users:
        # Планируем отправку через 30 минут - 1 час
        delay_minutes = random.uniform(30, 60)
        scheduled_at = datetime.now() + timedelta(minutes=delay_minutes)
        await db.schedule_followup(user['user_id'], 'clicked_payment', scheduled_at)
        logger.info(f"Scheduled 'clicked_payment' followup for user {user['user_id']} at {scheduled_at}")


# ==================== Auto-Broadcast System ====================

async def process_auto_broadcasts(bot: Bot):
    """
    Обработать все активные автоматические рассылки
    Вызывается периодически из scheduler
    
    Для каждой активной авто-рассылки:
    1. Получаем пользователей, которые подходят под триггер
    2. Проверяем, не отправляли ли мы им уже эту рассылку
    3. Отправляем сообщение и помечаем как отправленное
    """
    # Получаем все активные авто-рассылки
    auto_broadcasts = await db.get_auto_broadcasts(active_only=True)
    
    for auto_bc in auto_broadcasts:
        auto_id = auto_bc['id']
        trigger_type = auto_bc['trigger_type']
        delay_hours = auto_bc['delay_hours']
        content = auto_bc['content']
        
        # Получаем пользователей, подходящих под триггер
        eligible_users = await db.get_auto_broadcast_eligible_users(trigger_type, delay_hours)
        
        sent_count = 0
        for user in eligible_users:
            user_id = user['user_id']
            
            # Проверяем, не отправляли ли уже
            already_sent = await db.is_auto_broadcast_sent(auto_id, user_id)
            if already_sent:
                continue
            
            # Отправляем сообщение
            success = await send_broadcast_message(bot, user_id, content)
            
            if success:
                # Помечаем как отправленное
                await db.mark_auto_broadcast_sent(auto_id, user_id)
                await db.increment_auto_broadcast_sent(auto_id)
                sent_count += 1
                logger.info(f"Auto-broadcast {auto_id} sent to user {user_id}")
            
            # Небольшая задержка
            await asyncio.sleep(0.05)
        
        if sent_count > 0:
            logger.info(f"Auto-broadcast {auto_id} ({trigger_type}): sent to {sent_count} new users")

