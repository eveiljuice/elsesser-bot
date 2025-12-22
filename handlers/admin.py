import logging
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from aiogram import Router, Bot, F
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import database as db
from database import EventType
from config import ADMIN_USERNAMES, ADMIN_CHANNEL_ID
from keyboards.callbacks import (
    AdminCallback,
    AdminMenuCallback,
    AdminCaloriesCallback,
    AdminDayCallback,
    AdminMealCallback,
    AdminEditCallback,
    StatsDetailCallback,
    BroadcastMenuCallback,
    BroadcastAudienceCallback,
    BroadcastConfirmCallback,
    BroadcastScheduleCallback,
    BroadcastListCallback,
    TemplateMenuCallback,
    TemplateSelectCallback,
    TemplateSaveCallback,
    AutoBroadcastMenuCallback,
    AutoBroadcastTriggerCallback,
    AutoBroadcastDelayCallback,
    AutoBroadcastConfirmCallback,
    AutoBroadcastListCallback
)
from keyboards.user_kb import get_main_menu
from keyboards.calculator_kb import get_start_calculator_keyboard
from keyboards.admin_kb import (
    get_payment_verification_keyboard,
    get_admin_main_menu,
    get_admin_calories_keyboard,
    get_admin_days_keyboard,
    get_admin_meals_keyboard,
    get_admin_edit_keyboard,
    get_cancel_keyboard,
    get_stats_detail_keyboard,
    get_broadcast_menu_keyboard,
    get_broadcast_audience_keyboard,
    get_broadcast_schedule_keyboard,
    get_broadcast_confirm_keyboard,
    get_broadcast_list_keyboard,
    get_broadcast_view_keyboard,
    get_template_menu_keyboard,
    get_template_list_keyboard,
    get_template_view_keyboard,
    get_template_save_keyboard,
    get_auto_broadcast_menu_keyboard,
    get_auto_broadcast_trigger_keyboard,
    get_auto_broadcast_delay_keyboard,
    get_auto_broadcast_confirm_keyboard,
    get_auto_broadcast_list_keyboard,
    get_auto_broadcast_view_keyboard,
    get_skip_keyboard
)
from data.recipes import RECIPES, get_recipe_from_db

logger = logging.getLogger(__name__)
router = Router(name="admin")

# Екатеринбург timezone (UTC+5)
YEKATERINBURG_TZ = ZoneInfo("Asia/Yekaterinburg")


# ==================== FSM States ====================

class AdminEditState(StatesGroup):
    """Состояния для редактирования контента"""
    waiting_for_content = State()


class BroadcastState(StatesGroup):
    """Состояния для создания рассылки"""
    waiting_for_content = State()
    waiting_for_media = State()
    waiting_for_buttons = State()
    waiting_for_date = State()
    waiting_for_time = State()


class TemplateState(StatesGroup):
    """Состояния для создания шаблона"""
    waiting_for_content = State()
    waiting_for_media = State()
    waiting_for_buttons = State()
    waiting_for_name = State()


class AutoBroadcastState(StatesGroup):
    """Состояния для создания автоматической рассылки"""
    waiting_for_content = State()
    waiting_for_media = State()
    waiting_for_buttons = State()


# ==================== Helpers ====================

def is_admin(username: str) -> bool:
    """Проверка, является ли пользователь админом"""
    if not username:
        return False
    return username.lower() in [u.lower() for u in ADMIN_USERNAMES]


def format_raw_text_to_telegram(raw_text: str, meal_type: str) -> str:
    """
    Форматирует сырой текст в формат Telegram с HTML.

    Ожидаемый формат ввода:
    Название блюда

    Ингредиенты:
    - ингредиент 1
    - ингредиент 2

    Приготовление:
    1. шаг 1
    2. шаг 2

    КБЖУ: 300 ккал | Б: 20 г | Ж: 10 г | У: 30 г
    """
    meal_emoji = {
        "breakfast": "🌅",
        "lunch": "🍽",
        "dinner": "🌙"
    }
    meal_name = {
        "breakfast": "Завтрак",
        "lunch": "Обед",
        "dinner": "Ужин"
    }

    emoji = meal_emoji.get(meal_type, "🍴")
    name = meal_name.get(meal_type, "Приём пищи")

    lines = raw_text.strip().split('\n')
    if not lines:
        return raw_text

    # Первая непустая строка — название блюда
    title = ""
    content_start = 0
    for i, line in enumerate(lines):
        if line.strip():
            title = line.strip()
            content_start = i + 1
            break

    # Форматируем заголовок
    formatted = f"{emoji} <b>{name} — {title}</b>\n"

    # Остальной контент
    remaining = '\n'.join(lines[content_start:]).strip()

    # Заменяем заголовки секций
    remaining = re.sub(r'^(Ингредиенты:?)\s*$', r'\n<b>Ингредиенты:</b>',
                       remaining, flags=re.MULTILINE | re.IGNORECASE)
    remaining = re.sub(r'^(Приготовление:?)\s*$', r'\n<b>Приготовление:</b>',
                       remaining, flags=re.MULTILINE | re.IGNORECASE)
    remaining = re.sub(r'^(КБЖУ:?\s*)', r'\n<b>КБЖУ:</b> ',
                       remaining, flags=re.MULTILINE | re.IGNORECASE)

    # Заменяем маркеры списка на •
    remaining = re.sub(r'^[\-\*]\s*', '• ', remaining, flags=re.MULTILINE)

    formatted += remaining

    return formatted


# ==================== Admin Panel Entry ====================

@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    """Вход в админ-панель"""
    if not is_admin(message.from_user.username):
        await message.answer("⛔ У вас нет доступа к админ-панели.")
        return

    await state.clear()
    await message.answer(
        "👨‍💼 <b>Админ-панель</b>\n\n"
        "Выберите действие:",
        reply_markup=get_admin_main_menu(),
        parse_mode=ParseMode.HTML
    )


@router.message(F.text == "📝 Редактировать рационы")
async def edit_rations(message: Message, state: FSMContext):
    """Редактирование рационов"""
    if not is_admin(message.from_user.username):
        return

    await message.answer(
        "🔥 <b>Выберите калорийность для редактирования:</b>",
        reply_markup=get_admin_calories_keyboard(),
        parse_mode=ParseMode.HTML
    )


@router.message(F.text == "📊 Статистика")
async def show_stats(message: Message):
    """Показать расширенную статистику"""
    if not is_admin(message.from_user.username):
        return

    # Получаем статистику
    stats = await db.get_stats()
    custom_recipes = await db.get_all_custom_recipes()

    # Рассчитываем конверсии
    total = stats['total_users'] or 1  # избегаем деления на 0
    started = stats['started_users'] or total
    clicked = stats['clicked_payment_btn'] or 1

    conv_start_to_click = (
        stats['clicked_payment_btn'] / started * 100) if started else 0
    conv_click_to_screen = (
        stats['sent_screenshot'] / clicked * 100) if clicked else 0
    conv_start_to_paid = (stats['paid_users'] /
                          started * 100) if started else 0

    # Follow-up конверсия
    followup_users = stats.get('followup_users', 0) or 1
    followup_conv = (stats.get('paid_after_followup', 0) /
                     followup_users * 100) if followup_users else 0

    # Детализация по типам follow-up
    followup_by_type = stats.get('followup_by_type', {})
    only_start_sent = followup_by_type.get('only_start', 0)
    clicked_payment_sent = followup_by_type.get('clicked_payment', 0)

    await message.answer(
        "📊 <b>Статистика бота</b>\n\n"

        "👥 <b>Пользователи:</b>\n"
        f"├ Всего: <b>{stats['total_users']}</b>\n"
        f"├ 💰 Оплатили: <b>{stats['paid_users']}</b>\n"
        f"├ ⏳ Ожидают проверки: {stats['pending_payments']}\n"
        f"└ 📅 Новых за 7 дней: {stats['new_users_7d']}\n\n"

        "📈 <b>Воронка конверсии:</b>\n"
        f"├ /start: <b>{stats['started_users']}</b>\n"
        f"├ → Нажали «Я оплатила»: {stats['clicked_payment_btn']} ({conv_start_to_click:.1f}%)\n"
        f"├ → Прислали скрин: {stats['sent_screenshot']} ({conv_click_to_screen:.1f}%)\n"
        f"└ → Оплатили: {stats['paid_users']} ({conv_start_to_paid:.1f}%)\n\n"

        "🔍 <b>Потерянные клиенты:</b>\n"
        f"├ 😴 Только /start (ничего не делали): <b>{stats['only_start']}</b>\n"
        f"└ 🤔 Нажали оплату, но без скрина: <b>{stats['clicked_but_no_screenshot']}</b>\n\n"

        "📬 <b>Follow-up напоминания:</b>\n"
        f"├ 📤 Отправлено всего: {stats.get('followup_sent', 0)}\n"
        f"│   ├ «Только /start»: {only_start_sent}\n"
        f"│   └ «Нажали оплату»: {clicked_payment_sent}\n"
        f"├ 👤 Получили: {stats.get('followup_users', 0)} чел.\n"
        f"├ ✅ Оплатили после: <b>{stats.get('paid_after_followup', 0)}</b> ({followup_conv:.1f}%)\n"
        f"└ ❌ Проигнорировали: {stats.get('ignored_followup', 0)}\n\n"

        "📝 <b>Контент:</b>\n"
        f"├ Кастомных рецептов: {len(custom_recipes)}\n"
        f"├ Калорийностей в базе: {len(RECIPES)}\n"
        f"└ Всего дней рационов: {sum(len(days) for days in RECIPES.values())}\n\n"
        
        "👇 <b>Нажмите кнопку ниже для просмотра списков пользователей</b>",
        reply_markup=get_stats_detail_keyboard(),
        parse_mode=ParseMode.HTML
    )


@router.message(F.text == "📬 Отправить недельный отчёт")
async def send_weekly_report_manually(message: Message, bot: Bot):
    """Ручная отправка недельного отчёта в админ-чат"""
    if not is_admin(message.from_user.username):
        return

    if not ADMIN_CHANNEL_ID:
        await message.answer("❌ ADMIN_CHANNEL_ID не настроен в .env")
        return

    await message.answer("⏳ Формирую отчёт...")

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
            "🤖 <i>Отчёт сформирован вручную</i>\n\n"
            "👇 <b>Нажмите кнопку ниже для просмотра списков пользователей</b>"
        )

        await bot.send_message(
            chat_id=ADMIN_CHANNEL_ID,
            text=message_text,
            reply_markup=get_stats_detail_keyboard(),
            parse_mode=ParseMode.HTML
        )

        await message.answer(
            "✅ Недельный отчёт отправлен в админ-чат!",
            reply_markup=get_admin_main_menu()
        )
        logger.info(
            f"Weekly report sent manually by {message.from_user.username}")

    except Exception as e:
        logger.error(f"Failed to send weekly report manually: {e}")
        await message.answer(
            f"❌ Ошибка при отправке отчёта:\n<code>{e}</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=get_admin_main_menu()
        )


@router.message(F.text == "🔙 Выйти из админки")
async def exit_admin(message: Message, state: FSMContext):
    """Выход из админки"""
    if not is_admin(message.from_user.username):
        return

    await state.clear()
    await message.answer(
        "👋 Вы вышли из админ-панели.",
        reply_markup=get_main_menu(),
        parse_mode=ParseMode.HTML
    )


# ==================== Navigation ====================

@router.callback_query(AdminCaloriesCallback.filter())
async def admin_select_calories(callback: CallbackQuery, callback_data: AdminCaloriesCallback):
    """Выбор калорийности в админке"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    calories = callback_data.calories

    await callback.message.edit_text(
        f"📅 <b>Рацион {calories} ккал</b>\n\n"
        "Выберите день:",
        reply_markup=get_admin_days_keyboard(calories),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@router.callback_query(AdminDayCallback.filter())
async def admin_select_day(callback: CallbackQuery, callback_data: AdminDayCallback):
    """Выбор дня в админке"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    calories = callback_data.calories
    day = callback_data.day

    await callback.message.edit_text(
        f"🍽 <b>День {day} ({calories} ккал)</b>\n\n"
        "Выберите приём пищи для редактирования:",
        reply_markup=get_admin_meals_keyboard(calories, day),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@router.callback_query(AdminMealCallback.filter())
async def admin_select_meal(callback: CallbackQuery, callback_data: AdminMealCallback):
    """Выбор приёма пищи в админке"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    calories = callback_data.calories
    day = callback_data.day
    meal = callback_data.meal

    meal_names = {"breakfast": "Завтрак", "lunch": "Обед", "dinner": "Ужин"}

    # Проверяем, есть ли кастомный контент
    custom = await db.get_recipe(calories, day, meal)
    status = "✏️ (изменён)" if custom else "📄 (исходный)"

    await callback.message.edit_text(
        f"🍽 <b>{meal_names[meal]}</b> — День {day} ({calories} ккал)\n\n"
        f"Статус: {status}\n\n"
        "Выберите действие:",
        reply_markup=get_admin_edit_keyboard(calories, day, meal),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@router.callback_query(AdminMenuCallback.filter(F.action == "back"))
async def admin_back_to_calories(callback: CallbackQuery):
    """Назад к выбору калорийности"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    await callback.message.edit_text(
        "🔥 <b>Выберите калорийность для редактирования:</b>",
        reply_markup=get_admin_calories_keyboard(),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


# ==================== Edit Actions ====================

@router.callback_query(AdminEditCallback.filter(F.action == "edit"))
async def admin_start_edit(callback: CallbackQuery, callback_data: AdminEditCallback, state: FSMContext):
    """Начать редактирование"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    calories = callback_data.calories
    day = callback_data.day
    meal = callback_data.meal

    # Сохраняем данные в состояние
    await state.update_data(calories=calories, day=day, meal=meal)
    await state.set_state(AdminEditState.waiting_for_content)

    meal_names = {"breakfast": "Завтрак", "lunch": "Обед", "dinner": "Ужин"}

    await callback.message.answer(
        f"✏️ <b>Редактирование: {meal_names[meal]}</b>\n"
        f"День {day} ({calories} ккал)\n\n"
        "📝 <b>Отправьте текст в следующем формате:</b>\n\n"
        "<code>Название блюда\n\n"
        "Ингредиенты:\n"
        "- ингредиент 1 — количество\n"
        "- ингредиент 2 — количество\n\n"
        "Приготовление:\n"
        "1. Шаг первый\n"
        "2. Шаг второй\n\n"
        "КБЖУ: 300 ккал | Б: 20 г | Ж: 10 г | У: 30 г</code>\n\n"
        "💡 <i>Бот автоматически отформатирует текст!</i>",
        reply_markup=get_cancel_keyboard(),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@router.callback_query(AdminEditCallback.filter(F.action == "preview"))
async def admin_preview(callback: CallbackQuery, callback_data: AdminEditCallback):
    """Превью текущего контента"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    calories = callback_data.calories
    day = callback_data.day
    meal = callback_data.meal

    # Получаем текст (из БД или дефолтный)
    content = await get_recipe_from_db(calories, day, meal)

    if not content:
        await callback.answer("❌ Контент не найден", show_alert=True)
        return

    await callback.message.answer(
        f"👁 <b>Превью:</b>\n\n{content}",
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@router.callback_query(AdminEditCallback.filter(F.action == "reset"))
async def admin_reset(callback: CallbackQuery, callback_data: AdminEditCallback):
    """Сбросить к исходному тексту"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    calories = callback_data.calories
    day = callback_data.day
    meal = callback_data.meal

    deleted = await db.delete_recipe(calories, day, meal)

    if deleted:
        await callback.answer("✅ Сброшено к исходному!", show_alert=True)

        # Обновляем статус в сообщении
        meal_names = {"breakfast": "Завтрак",
                      "lunch": "Обед", "dinner": "Ужин"}
        await callback.message.edit_text(
            f"🍽 <b>{meal_names[meal]}</b> — День {day} ({calories} ккал)\n\n"
            "Статус: 📄 (исходный)\n\n"
            "Выберите действие:",
            reply_markup=get_admin_edit_keyboard(calories, day, meal),
            parse_mode=ParseMode.HTML
        )
    else:
        await callback.answer("ℹ️ Уже используется исходный текст", show_alert=True)


# ==================== FSM: Receive Content ====================

@router.message(F.text == "❌ Отмена", AdminEditState.waiting_for_content)
async def cancel_edit(message: Message, state: FSMContext):
    """Отмена редактирования"""
    if not is_admin(message.from_user.username):
        return

    await state.clear()
    await message.answer(
        "❌ Редактирование отменено.",
        reply_markup=get_admin_main_menu(),
        parse_mode=ParseMode.HTML
    )


@router.message(AdminEditState.waiting_for_content)
async def receive_content(message: Message, state: FSMContext):
    """Получение нового контента"""
    if not is_admin(message.from_user.username):
        return

    data = await state.get_data()
    calories = data['calories']
    day = data['day']
    meal = data['meal']

    # Форматируем текст
    formatted_content = format_raw_text_to_telegram(message.text, meal)

    # Сохраняем в БД
    await db.save_recipe(
        calories=calories,
        day=day,
        meal_type=meal,
        content=formatted_content,
        updated_by=message.from_user.username
    )

    await state.clear()

    meal_names = {"breakfast": "Завтрак", "lunch": "Обед", "dinner": "Ужин"}

    await message.answer(
        f"✅ <b>Сохранено!</b>\n\n"
        f"📍 {meal_names[meal]} — День {day} ({calories} ккал)\n\n"
        f"<b>Превью:</b>\n\n{formatted_content}",
        reply_markup=get_admin_main_menu(),
        parse_mode=ParseMode.HTML
    )


# ==================== Payment Verification (existing) ====================

@router.callback_query(AdminCallback.filter(F.action == "approve"))
async def approve_payment(callback: CallbackQuery, callback_data: AdminCallback, bot: Bot):
    """Админ подтвердил оплату"""
    user_id = callback_data.user_id
    request_id = callback_data.request_id
    product_type = callback_data.product_type

    logger.info(
        f"Admin {callback.from_user.id} approving payment: user_id={user_id}, request_id={request_id}, product={product_type}")

    # Получаем информацию о запросе
    request = await db.get_payment_request(request_id)
    if not request:
        logger.warning(f"Payment request {request_id} not found in database")
        await callback.answer(
            "❌ Запрос не найден в базе!\nВозможно, это старый запрос или бот был перезапущен.",
            show_alert=True
        )
        return

    if request['status'] != 'pending':
        logger.info(
            f"Payment request {request_id} already processed: status={request['status']}")
        await callback.answer(
            f"⚠️ Этот запрос уже обработан!\nСтатус: {request['status']}",
            show_alert=True
        )
        return

    logger.info(f"Processing payment approval for user {user_id}, product {product_type}")

    # Обновляем статус оплаты пользователя в зависимости от типа продукта
    if product_type == 'fmd':
        await db.set_fmd_payment_status(user_id, True)
    else:
        await db.set_payment_status(user_id, True)
    
    await db.update_payment_request(request_id, 'approved')

    # Логируем событие и отменяем все pending follow-up сообщения
    await db.log_event(user_id, EventType.PAYMENT_APPROVED, f"approved_by:{callback.from_user.id},product:{product_type}")
    await db.cancel_user_followups(user_id)

    # Получаем информацию о пользователе
    user = await db.get_user(user_id)

    # Формируем отображение для админа, кто обработал
    if callback.from_user.username:
        admin_display = f"@{callback.from_user.username}"
    else:
        admin_name = f"{callback.from_user.first_name or ''} {callback.from_user.last_name or ''}".strip(
        ) or f"Admin {callback.from_user.id}"
        admin_display = f'<a href="tg://user?id={callback.from_user.id}">{admin_name}</a>'

    # Обновляем сообщение в админском канале
    # Проверяем, это фото (со скриншотом) или текстовое сообщение
    original_text = callback.message.caption or callback.message.text or ""
    new_text = original_text + \
        f"\n\n✅ <b>ОДОБРЕНО</b>\n👤 Обработал: {admin_display}"

    if callback.message.photo:
        # Сообщение с фото - редактируем caption
        await callback.message.edit_caption(
            caption=new_text,
            parse_mode=ParseMode.HTML
        )
    else:
        # Текстовое сообщение
        await callback.message.edit_text(
            new_text,
            parse_mode=ParseMode.HTML
        )

    # Уведомляем пользователя
    try:
        if product_type == 'fmd':
            # FMD протокол
            await bot.send_message(
                chat_id=user_id,
                text=(
                    "🎉 <b>Оплата FMD Протокола подтверждена!</b>\n\n"
                    "Теперь у тебя есть доступ к 5-дневной программе FMD!\n\n"
                    "🥗 Нажми «🍽 Выбрать рацион» → «FMD Протокол» чтобы начать."
                ),
                reply_markup=get_main_menu(),
                parse_mode=ParseMode.HTML
            )
        else:
            # Основной рацион
            await bot.send_message(
                chat_id=user_id,
                text=(
                    "🎉 <b>Оплата подтверждена!</b>\n\n"
                    "Теперь у тебя есть полный доступ ко всем рационам питания!"
                ),
                reply_markup=get_main_menu(),
                parse_mode=ParseMode.HTML
            )

            # Для основного рациона предлагаем пройти калькулятор
            await bot.send_message(
                chat_id=user_id,
                text=(
                    "📊 <b>Определи свой идеальный рацион!</b>\n\n"
                    "Чтобы подобрать рацион, который подходит именно тебе, "
                    "пройди короткую анкету. Калькулятор рассчитает:\n\n"
                    "• 🔥 Твою дневную калорийность\n"
                    "• 🥩 Норму белков, жиров и углеводов\n"
                    "• ⚖️ Оптимальный вес\n"
                    "• 📏 Индекс массы тела\n\n"
                    "Это займёт всего 2 минуты 👇"
                ),
                reply_markup=get_start_calculator_keyboard(),
                parse_mode=ParseMode.HTML
            )

        logger.info(
            f"Payment approved for user {user_id} (product={product_type}) by admin {callback.from_user.id}")
    except Exception as e:
        logger.error(f"Failed to notify user {user_id}: {e}")
        await callback.answer(
            f"✅ Оплата одобрена, но не удалось уведомить пользователя",
            show_alert=True
        )
        return

    await callback.answer("✅ Оплата одобрена!")


@router.callback_query(AdminCallback.filter(F.action == "reject"))
async def reject_payment(callback: CallbackQuery, callback_data: AdminCallback, bot: Bot):
    """Админ отклонил оплату"""
    user_id = callback_data.user_id
    request_id = callback_data.request_id
    product_type = callback_data.product_type

    # Получаем информацию о запросе
    request = await db.get_payment_request(request_id)
    if not request:
        await callback.answer("❌ Запрос не найден!", show_alert=True)
        return

    if request['status'] != 'pending':
        await callback.answer("⚠️ Этот запрос уже обработан!", show_alert=True)
        return

    # Обновляем статус запроса
    await db.update_payment_request(request_id, 'rejected')

    # Логируем событие отклонения
    await db.log_event(user_id, EventType.PAYMENT_REJECTED, f"rejected_by:{callback.from_user.id},product:{product_type}")

    # Получаем информацию о пользователе
    user = await db.get_user(user_id)

    # Формируем отображение для админа, кто обработал
    if callback.from_user.username:
        admin_display = f"@{callback.from_user.username}"
    else:
        admin_name = f"{callback.from_user.first_name or ''} {callback.from_user.last_name or ''}".strip(
        ) or f"Admin {callback.from_user.id}"
        admin_display = f'<a href="tg://user?id={callback.from_user.id}">{admin_name}</a>'

    # Обновляем сообщение в админском канале
    # Проверяем, это фото (со скриншотом) или текстовое сообщение
    original_text = callback.message.caption or callback.message.text or ""
    new_text = original_text + \
        f"\n\n❌ <b>ОТКЛОНЕНО</b>\n👤 Обработал: {admin_display}"

    if callback.message.photo:
        # Сообщение с фото - редактируем caption
        await callback.message.edit_caption(
            caption=new_text,
            parse_mode=ParseMode.HTML
        )
    else:
        # Текстовое сообщение
        await callback.message.edit_text(
            new_text,
            parse_mode=ParseMode.HTML
        )

    # Уведомляем пользователя
    try:
        product_name = "FMD Протокола" if product_type == 'fmd' else "рациона"
        await bot.send_message(
            chat_id=user_id,
            text=(
                f"❌ <b>Оплата {product_name} не подтверждена</b>\n\n"
                "К сожалению, мы не смогли найти вашу оплату.\n\n"
                "Возможные причины:\n"
                "• Оплата ещё не поступила\n"
                "• Неверная сумма\n"
                "• Оплата по другим реквизитам\n\n"
                "Пожалуйста, проверьте данные и попробуйте снова.\n"
                "Если у вас есть вопросы — обратитесь к администратору."
            ),
            parse_mode=ParseMode.HTML
        )
        logger.info(
            f"Payment rejected for user {user_id} (product={product_type}) by admin {callback.from_user.id}")
    except Exception as e:
        logger.error(f"Failed to notify user {user_id}: {e}")
        await callback.answer(
            f"❌ Оплата отклонена, но не удалось уведомить пользователя",
            show_alert=True
        )
        return

    await callback.answer("❌ Оплата отклонена")


# ==================== Detailed Statistics ====================

@router.callback_query(StatsDetailCallback.filter())
async def show_detailed_users(callback: CallbackQuery, callback_data: StatsDetailCallback):
    """Показать детальный список пользователей по статусу"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    status_type = callback_data.status_type
    
    # Получаем пользователей по статусу
    users = await db.get_users_by_status(status_type)
    
    # Названия для разных статусов
    status_titles = {
        "paid": "💰 Оплатили",
        "pending": "⏳ Ожидают проверки",
        "rejected": "❌ Отклонены",
        "only_start": "😴 Только /start",
        "clicked_no_screenshot": "🤔 Нажали оплату без скрина",
        "all_users": "👥 Все пользователи"
    }
    
    title = status_titles.get(status_type, "Пользователи")
    
    if not users:
        await callback.answer(
            f"📭 {title}: список пуст",
            show_alert=True
        )
        return
    
    # Формируем список пользователей
    user_lines = []
    for user in users:
        username = user.get('username')
        first_name = user.get('first_name', 'Без имени')
        user_id = user.get('user_id')
        
        # Формируем ссылку на пользователя
        if username:
            user_display = f"@{username}"
        else:
            user_display = f'<a href="tg://user?id={user_id}">{first_name}</a>'
        
        user_lines.append(user_display)
    
    # Делим на части если список слишком большой (Telegram лимит ~4096 символов)
    max_users_per_message = 100
    total_users = len(user_lines)
    
    if total_users <= max_users_per_message:
        # Все помещается в одно сообщение
        users_text = "\n".join(user_lines)
        message_text = (
            f"<b>{title}</b>\n"
            f"Всего: {total_users}\n\n"
            f"{users_text}"
        )
        
        await callback.message.answer(
            message_text,
            parse_mode=ParseMode.HTML
        )
    else:
        # Разбиваем на несколько сообщений
        chunks = [user_lines[i:i + max_users_per_message] 
                  for i in range(0, total_users, max_users_per_message)]
        
        for idx, chunk in enumerate(chunks, 1):
            users_text = "\n".join(chunk)
            message_text = (
                f"<b>{title}</b> (часть {idx}/{len(chunks)})\n"
                f"Всего: {total_users}\n\n"
                f"{users_text}"
            )
            
            await callback.message.answer(
                message_text,
                parse_mode=ParseMode.HTML
            )
    
    await callback.answer()


# ==================== Broadcast Management ====================

def get_audience_display_name(audience: str) -> str:
    """Получить отображаемое название аудитории"""
    names = {
        'all': '👥 Все пользователи',
        'start_only': '👆 Только /start (ничего не делали)',
        'rejected': '❌ Отклонённые оплаты',
        'no_screenshot': '🤔 Нажали оплату без скрина'
    }
    return names.get(audience, audience)


@router.message(F.text == "📣 Управление рассылками")
async def broadcast_menu(message: Message, state: FSMContext):
    """Вход в меню рассылок"""
    if not is_admin(message.from_user.username):
        return

    await state.clear()
    await message.answer(
        "📣 <b>Управление рассылками</b>\n\n"
        "Здесь вы можете создавать и управлять рассылками для пользователей.",
        reply_markup=get_broadcast_menu_keyboard(),
        parse_mode=ParseMode.HTML
    )


@router.callback_query(BroadcastMenuCallback.filter(F.action == "create"))
async def broadcast_start_create(callback: CallbackQuery, state: FSMContext):
    """Начать создание рассылки"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    await state.set_state(BroadcastState.waiting_for_content)
    
    await callback.message.edit_text(
        "📝 <b>Создание рассылки</b>\n\n"
        "Отправьте текст рассылки.\n\n"
        "💡 <i>Можете использовать HTML-форматирование:</i>\n"
        "<code>&lt;b&gt;жирный&lt;/b&gt;</code>\n"
        "<code>&lt;i&gt;курсив&lt;/i&gt;</code>\n"
        "<code>&lt;u&gt;подчёркнутый&lt;/u&gt;</code>\n"
        "<code>&lt;a href=\"URL\"&gt;ссылка&lt;/a&gt;</code>",
        parse_mode=ParseMode.HTML
    )
    
    await callback.message.answer(
        "❌ Отмена",
        reply_markup=get_cancel_keyboard(),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@router.callback_query(BroadcastMenuCallback.filter(F.action == "list"))
async def broadcast_show_list(callback: CallbackQuery):
    """Показать список запланированных рассылок"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    broadcasts = await db.get_scheduled_broadcasts()
    
    if not broadcasts:
        await callback.answer("📭 Нет запланированных рассылок", show_alert=True)
        return
    
    await callback.message.edit_text(
        "📋 <b>Запланированные рассылки</b>\n\n"
        f"Всего: {len(broadcasts)}",
        reply_markup=get_broadcast_list_keyboard(broadcasts),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@router.callback_query(BroadcastMenuCallback.filter(F.action == "back"))
async def broadcast_back_to_menu(callback: CallbackQuery, state: FSMContext):
    """Вернуться в меню рассылок"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    await state.clear()
    await callback.message.edit_text(
        "📣 <b>Управление рассылками</b>\n\n"
        "Здесь вы можете создавать и управлять рассылками для пользователей.",
        reply_markup=get_broadcast_menu_keyboard(),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@router.message(F.text == "❌ Отмена", BroadcastState.waiting_for_content)
@router.message(F.text == "❌ Отмена", BroadcastState.waiting_for_date)
@router.message(F.text == "❌ Отмена", BroadcastState.waiting_for_time)
async def broadcast_cancel(message: Message, state: FSMContext):
    """Отмена создания рассылки"""
    if not is_admin(message.from_user.username):
        return

    await state.clear()
    await message.answer(
        "❌ Создание рассылки отменено.",
        reply_markup=get_admin_main_menu(),
        parse_mode=ParseMode.HTML
    )
    await message.answer(
        "📣 <b>Управление рассылками</b>\n\n"
        "Здесь вы можете создавать и управлять рассылками для пользователей.",
        reply_markup=get_broadcast_menu_keyboard(),
        parse_mode=ParseMode.HTML
    )


@router.message(BroadcastState.waiting_for_content)
async def broadcast_receive_content(message: Message, state: FSMContext):
    """Получение текста рассылки"""
    if not is_admin(message.from_user.username):
        return

    # Используем html_text для сохранения форматирования (жирный, курсив и т.д.)
    content = message.html_text
    
    # Сохраняем текст в состояние
    await state.update_data(content=content)
    
    # Спрашиваем про медиа
    await state.set_state(BroadcastState.waiting_for_media)
    await message.answer(
        "📸 <b>Добавление медиа (опционально)</b>\n\n"
        "Отправьте фото или видео, которое хотите добавить к рассылке.\n\n"
        "Или нажмите <b>Пропустить</b>, если медиа не нужно.",
        reply_markup=get_skip_keyboard(),
        parse_mode=ParseMode.HTML
    )


@router.message(BroadcastState.waiting_for_media, F.text == "⏭ Пропустить")
async def broadcast_skip_media(message: Message, state: FSMContext):
    """Пропуск добавления медиа"""
    if not is_admin(message.from_user.username):
        return
    
    # Переходим к кнопкам
    await state.set_state(BroadcastState.waiting_for_buttons)
    await message.answer(
        "🔘 <b>Добавление кнопок (опционально)</b>\n\n"
        "Отправьте кнопки в формате:\n"
        "<code>Текст кнопки 1 | https://example.com\n"
        "Текст кнопки 2 | /start</code>\n\n"
        "Каждая строка — одна кнопка.\n"
        "Используйте <code>|</code> для разделения текста и ссылки/команды.\n\n"
        "Или нажмите <b>Пропустить</b>.",
        reply_markup=get_skip_keyboard(),
        parse_mode=ParseMode.HTML
    )


@router.message(BroadcastState.waiting_for_media, F.photo | F.video)
async def broadcast_receive_media(message: Message, state: FSMContext):
    """Получение медиа для рассылки"""
    if not is_admin(message.from_user.username):
        return
    
    # Определяем тип медиа и file_id
    if message.photo:
        media_type = 'photo'
        media_file_id = message.photo[-1].file_id  # Берём фото максимального размера
    elif message.video:
        media_type = 'video'
        media_file_id = message.video.file_id
    else:
        await message.answer("❌ Пожалуйста, отправьте фото или видео.")
        return
    
    # Сохраняем медиа в состояние
    await state.update_data(media_type=media_type, media_file_id=media_file_id)
    
    # Переходим к кнопкам
    await state.set_state(BroadcastState.waiting_for_buttons)
    await message.answer(
        "✅ Медиа добавлено!\n\n"
        "🔘 <b>Добавление кнопок (опционально)</b>\n\n"
        "Отправьте кнопки в формате:\n"
        "<code>Текст кнопки 1 | https://example.com\n"
        "Текст кнопки 2 | /start</code>\n\n"
        "Каждая строка — одна кнопка.\n"
        "Используйте <code>|</code> для разделения текста и ссылки/команды.\n\n"
        "Или нажмите <b>Пропустить</b>.",
        reply_markup=get_skip_keyboard(),
        parse_mode=ParseMode.HTML
    )


@router.message(BroadcastState.waiting_for_buttons, F.text == "⏭ Пропустить")
async def broadcast_skip_buttons(message: Message, state: FSMContext):
    """Пропуск добавления кнопок"""
    if not is_admin(message.from_user.username):
        return
    
    # Получаем данные для превью
    data = await state.get_data()
    content = data.get('content', '')
    
    # Переходим к выбору аудитории
    await message.answer(
        "👁 <b>Превью рассылки:</b>\n\n"
        f"{content}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🎯 <b>Выберите аудиторию рассылки:</b>",
        reply_markup=get_broadcast_audience_keyboard(),
        parse_mode=ParseMode.HTML
    )


@router.message(BroadcastState.waiting_for_buttons)
async def broadcast_receive_buttons(message: Message, state: FSMContext):
    """Получение кнопок для рассылки"""
    if not is_admin(message.from_user.username):
        return
    
    import json
    
    # Парсим кнопки из текста
    lines = message.text.strip().split('\n')
    buttons_data = []
    
    for line in lines:
        if '|' not in line:
            continue
        
        parts = line.split('|', 1)
        text = parts[0].strip()
        target = parts[1].strip()
        
        # Определяем тип кнопки (url или callback_data)
        if target.startswith('http://') or target.startswith('https://'):
            buttons_data.append([{"text": text, "url": target}])
        else:
            buttons_data.append([{"text": text, "callback_data": target}])
    
    if not buttons_data:
        await message.answer(
            "❌ Не удалось распознать кнопки. Попробуйте ещё раз или нажмите <b>Пропустить</b>.",
            reply_markup=get_skip_keyboard(),
            parse_mode=ParseMode.HTML
        )
        return
    
    # Сохраняем кнопки в JSON
    buttons_json = json.dumps(buttons_data, ensure_ascii=False)
    await state.update_data(buttons=buttons_json)
    
    # Получаем данные для превью
    data = await state.get_data()
    content = data.get('content', '')
    
    # Переходим к выбору аудитории
    await message.answer(
        f"✅ Кнопки добавлены: {len(buttons_data)} шт.\n\n"
        "👁 <b>Превью рассылки:</b>\n\n"
        f"{content}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🎯 <b>Выберите аудиторию рассылки:</b>",
        reply_markup=get_broadcast_audience_keyboard(),
        parse_mode=ParseMode.HTML
    )


@router.callback_query(BroadcastAudienceCallback.filter())
async def broadcast_select_audience(callback: CallbackQuery, callback_data: BroadcastAudienceCallback, state: FSMContext):
    """Выбор аудитории рассылки"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    audience = callback_data.audience
    
    # Получаем количество пользователей
    user_count = await db.get_broadcast_audience_count(audience)
    
    # Сохраняем аудиторию
    await state.update_data(audience=audience, user_count=user_count)
    
    # Получаем данные для превью
    data = await state.get_data()
    content = data.get('content', '')
    
    audience_name = get_audience_display_name(audience)
    
    await callback.message.edit_text(
        "📨 <b>Превью рассылки</b>\n\n"
        f"{content}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🎯 <b>Аудитория:</b> {audience_name}\n"
        f"👥 <b>Получателей:</b> {user_count} чел.\n\n"
        "⏰ <b>Выберите время отправки:</b>",
        reply_markup=get_broadcast_schedule_keyboard(),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@router.callback_query(BroadcastScheduleCallback.filter(F.action == "now"))
async def broadcast_send_now(callback: CallbackQuery, state: FSMContext):
    """Отправить рассылку сейчас"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    data = await state.get_data()
    content = data.get('content', '')
    audience = data.get('audience', 'all')
    user_count = data.get('user_count', 0)
    
    # Устанавливаем время "сейчас"
    now = datetime.now(YEKATERINBURG_TZ)
    await state.update_data(scheduled_at=now)
    
    audience_name = get_audience_display_name(audience)
    
    await callback.message.edit_text(
        "🚀 <b>ФИНАЛЬНОЕ ПОДТВЕРЖДЕНИЕ</b>\n\n"
        f"📝 <b>Текст рассылки:</b>\n{content}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🎯 <b>Аудитория:</b> {audience_name}\n"
        f"👥 <b>Получателей:</b> {user_count} чел.\n"
        f"⏰ <b>Отправка:</b> Сейчас\n\n"
        "⚠️ <b>Проверьте всё внимательно!</b>\n"
        "После подтверждения рассылка будет отправлена немедленно.",
        reply_markup=get_broadcast_confirm_keyboard(),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@router.callback_query(BroadcastScheduleCallback.filter(F.action == "schedule"))
async def broadcast_schedule(callback: CallbackQuery, state: FSMContext):
    """Запланировать рассылку"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    await state.set_state(BroadcastState.waiting_for_date)
    
    now = datetime.now(YEKATERINBURG_TZ)
    
    await callback.message.edit_text(
        "📅 <b>Выберите дату отправки</b>\n\n"
        f"Текущая дата (Екатеринбург): <b>{now.strftime('%d.%m.%Y')}</b>\n\n"
        "Отправьте дату в формате <code>ДД.ММ.ГГГГ</code>\n"
        "Например: <code>25.12.2025</code>",
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@router.message(BroadcastState.waiting_for_date)
async def broadcast_receive_date(message: Message, state: FSMContext):
    """Получение даты рассылки"""
    if not is_admin(message.from_user.username):
        return

    date_str = message.text.strip()
    
    # Парсим дату
    try:
        date = datetime.strptime(date_str, "%d.%m.%Y")
        
        # Проверяем что дата не в прошлом
        now = datetime.now(YEKATERINBURG_TZ)
        if date.date() < now.date():
            await message.answer(
                "❌ Дата не может быть в прошлом!\n\n"
                "Отправьте корректную дату в формате <code>ДД.ММ.ГГГГ</code>",
                parse_mode=ParseMode.HTML
            )
            return
        
        await state.update_data(date=date_str)
        await state.set_state(BroadcastState.waiting_for_time)
        
        await message.answer(
            f"📅 Дата: <b>{date_str}</b>\n\n"
            "⏰ <b>Выберите время отправки</b>\n\n"
            f"Текущее время (Екатеринбург): <b>{now.strftime('%H:%M')}</b>\n\n"
            "Отправьте время в формате <code>ЧЧ:ММ</code>\n"
            "Например: <code>14:30</code>",
            parse_mode=ParseMode.HTML
        )
    except ValueError:
        await message.answer(
            "❌ Неверный формат даты!\n\n"
            "Отправьте дату в формате <code>ДД.ММ.ГГГГ</code>\n"
            "Например: <code>25.12.2025</code>",
            parse_mode=ParseMode.HTML
        )


@router.message(BroadcastState.waiting_for_time)
async def broadcast_receive_time(message: Message, state: FSMContext):
    """Получение времени рассылки"""
    if not is_admin(message.from_user.username):
        return

    time_str = message.text.strip()
    
    # Парсим время
    try:
        time = datetime.strptime(time_str, "%H:%M")
        
        data = await state.get_data()
        date_str = data.get('date')
        content = data.get('content', '')
        audience = data.get('audience', 'all')
        user_count = data.get('user_count', 0)
        
        # Собираем полную дату и время
        date = datetime.strptime(date_str, "%d.%m.%Y")
        scheduled_at = datetime(
            year=date.year,
            month=date.month,
            day=date.day,
            hour=time.hour,
            minute=time.minute,
            tzinfo=YEKATERINBURG_TZ
        )
        
        # Проверяем что время не в прошлом
        now = datetime.now(YEKATERINBURG_TZ)
        if scheduled_at <= now:
            await message.answer(
                "❌ Время не может быть в прошлом!\n\n"
                "Отправьте корректное время в формате <code>ЧЧ:ММ</code>",
                parse_mode=ParseMode.HTML
            )
            return
        
        await state.update_data(scheduled_at=scheduled_at)
        await state.set_state(None)  # Сбрасываем состояние
        
        audience_name = get_audience_display_name(audience)
        scheduled_str = scheduled_at.strftime('%d.%m.%Y в %H:%M')
        
        await message.answer(
            "🚀 <b>ФИНАЛЬНОЕ ПОДТВЕРЖДЕНИЕ</b>\n\n"
            f"📝 <b>Текст рассылки:</b>\n{content}\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🎯 <b>Аудитория:</b> {audience_name}\n"
            f"👥 <b>Получателей:</b> {user_count} чел.\n"
            f"⏰ <b>Отправка:</b> {scheduled_str} (Екатеринбург)\n\n"
            "⚠️ <b>Проверьте всё внимательно!</b>\n"
            "После подтверждения рассылка будет запланирована.",
            reply_markup=get_broadcast_confirm_keyboard(),
            parse_mode=ParseMode.HTML
        )
    except ValueError:
        await message.answer(
            "❌ Неверный формат времени!\n\n"
            "Отправьте время в формате <code>ЧЧ:ММ</code>\n"
            "Например: <code>14:30</code>",
            parse_mode=ParseMode.HTML
        )


@router.callback_query(BroadcastConfirmCallback.filter(F.action == "confirm"))
async def broadcast_confirm(callback: CallbackQuery, state: FSMContext):
    """Подтверждение и создание рассылки"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    data = await state.get_data()
    content = data.get('content', '')
    audience = data.get('audience', 'all')
    scheduled_at = data.get('scheduled_at')
    media_type = data.get('media_type')
    media_file_id = data.get('media_file_id')
    buttons = data.get('buttons')
    
    if not content or not scheduled_at:
        await callback.answer("❌ Ошибка: данные рассылки утеряны", show_alert=True)
        return
    
    # Конвертируем в UTC для хранения в БД
    if isinstance(scheduled_at, datetime) and scheduled_at.tzinfo:
        scheduled_at_utc = scheduled_at.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
    else:
        scheduled_at_utc = scheduled_at
    
    # Создаём рассылку в БД
    broadcast_id = await db.create_broadcast(
        content=content,
        audience=audience,
        scheduled_at=scheduled_at_utc,
        created_by=callback.from_user.id,
        created_by_username=callback.from_user.username,
        media_type=media_type,
        media_file_id=media_file_id,
        buttons=buttons
    )
    
    await state.clear()
    
    audience_name = get_audience_display_name(audience)
    user_count = await db.get_broadcast_audience_count(audience)
    
    if isinstance(scheduled_at, datetime):
        if scheduled_at.tzinfo:
            scheduled_str = scheduled_at.strftime('%d.%m.%Y в %H:%M')
        else:
            scheduled_str = "Сейчас"
    else:
        scheduled_str = "Сейчас"
    
    await callback.message.edit_text(
        "✅ <b>Рассылка создана!</b>\n\n"
        f"📨 ID: <code>{broadcast_id}</code>\n"
        f"🎯 Аудитория: {audience_name}\n"
        f"👥 Получателей: {user_count} чел.\n"
        f"⏰ Отправка: {scheduled_str}\n\n"
        "Рассылка будет отправлена автоматически в указанное время.",
        reply_markup=get_broadcast_menu_keyboard(),
        parse_mode=ParseMode.HTML
    )
    
    logger.info(f"Broadcast {broadcast_id} created by {callback.from_user.username}")
    await callback.answer("✅ Рассылка создана!")


@router.callback_query(BroadcastConfirmCallback.filter(F.action == "edit"))
async def broadcast_edit(callback: CallbackQuery, state: FSMContext):
    """Редактирование текста рассылки"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    await state.set_state(BroadcastState.waiting_for_content)
    
    await callback.message.edit_text(
        "✏️ <b>Редактирование рассылки</b>\n\n"
        "Отправьте новый текст рассылки.",
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@router.callback_query(BroadcastConfirmCallback.filter(F.action == "cancel"))
async def broadcast_cancel_create(callback: CallbackQuery, state: FSMContext):
    """Отмена создания рассылки"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    await state.clear()
    
    await callback.message.edit_text(
        "❌ Создание рассылки отменено.\n\n"
        "📣 <b>Управление рассылками</b>\n\n"
        "Здесь вы можете создавать и управлять рассылками для пользователей.",
        reply_markup=get_broadcast_menu_keyboard(),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@router.callback_query(BroadcastListCallback.filter(F.action == "view"))
async def broadcast_view(callback: CallbackQuery, callback_data: BroadcastListCallback):
    """Просмотр конкретной рассылки"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    broadcast_id = callback_data.broadcast_id
    broadcast = await db.get_broadcast(broadcast_id)
    
    if not broadcast:
        await callback.answer("❌ Рассылка не найдена", show_alert=True)
        return
    
    content = broadcast['content']
    audience = broadcast['audience']
    scheduled_at = broadcast['scheduled_at']
    status = broadcast['status']
    created_by_username = broadcast.get('created_by_username', 'Unknown')
    
    audience_name = get_audience_display_name(audience)
    user_count = await db.get_broadcast_audience_count(audience)
    
    # Парсим дату и конвертируем в Екатеринбург
    try:
        dt = datetime.fromisoformat(scheduled_at)
        dt_ekb = dt.replace(tzinfo=ZoneInfo("UTC")).astimezone(YEKATERINBURG_TZ)
        scheduled_str = dt_ekb.strftime('%d.%m.%Y в %H:%M')
    except:
        scheduled_str = scheduled_at
    
    status_names = {
        'pending': '⏳ Ожидает отправки',
        'sending': '📤 Отправляется...',
        'sent': '✅ Отправлена',
        'cancelled': '❌ Отменена'
    }
    status_name = status_names.get(status, status)
    
    await callback.message.edit_text(
        f"📨 <b>Рассылка #{broadcast_id}</b>\n\n"
        f"📝 <b>Текст:</b>\n{content}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🎯 <b>Аудитория:</b> {audience_name}\n"
        f"👥 <b>Получателей:</b> {user_count} чел.\n"
        f"⏰ <b>Отправка:</b> {scheduled_str} (Екатеринбург)\n"
        f"📊 <b>Статус:</b> {status_name}\n"
        f"👤 <b>Создал:</b> @{created_by_username}",
        reply_markup=get_broadcast_view_keyboard(broadcast_id),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@router.callback_query(BroadcastListCallback.filter(F.action == "cancel"))
async def broadcast_cancel_scheduled(callback: CallbackQuery, callback_data: BroadcastListCallback):
    """Отмена запланированной рассылки"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    broadcast_id = callback_data.broadcast_id
    cancelled = await db.cancel_broadcast(broadcast_id)
    
    if cancelled:
        logger.info(f"Broadcast {broadcast_id} cancelled by {callback.from_user.username}")
        await callback.answer("✅ Рассылка отменена!", show_alert=True)
        
        # Показываем обновлённый список
        broadcasts = await db.get_scheduled_broadcasts()
        
        if not broadcasts:
            await callback.message.edit_text(
                "📣 <b>Управление рассылками</b>\n\n"
                "📭 Нет запланированных рассылок.",
                reply_markup=get_broadcast_menu_keyboard(),
                parse_mode=ParseMode.HTML
            )
        else:
            await callback.message.edit_text(
                "📋 <b>Запланированные рассылки</b>\n\n"
                f"Всего: {len(broadcasts)}",
                reply_markup=get_broadcast_list_keyboard(broadcasts),
                parse_mode=ParseMode.HTML
            )
    else:
        await callback.answer("❌ Не удалось отменить рассылку", show_alert=True)


@router.callback_query(BroadcastListCallback.filter(F.action == "page"))
async def broadcast_list_page(callback: CallbackQuery, callback_data: BroadcastListCallback):
    """Пагинация списка рассылок"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    page = callback_data.page
    broadcasts = await db.get_scheduled_broadcasts()
    
    await callback.message.edit_text(
        "📋 <b>Запланированные рассылки</b>\n\n"
        f"Всего: {len(broadcasts)}",
        reply_markup=get_broadcast_list_keyboard(broadcasts, page),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


# ==================== Template Management ====================

def get_trigger_display_name(trigger: str) -> str:
    """Получить отображаемое название триггера"""
    names = {
        'only_start': '👆 Только /start (ничего не делали)',
        'no_payment': '💳 Не оплатили (после клика оплатить)',
        'rejected': '❌ Отклонённая оплата',
        'no_screenshot': '🤔 Нажали оплатить без скрина'
    }
    return names.get(trigger, trigger)


@router.callback_query(TemplateMenuCallback.filter(F.action == "list"))
async def template_show_menu(callback: CallbackQuery, state: FSMContext):
    """Показать меню шаблонов"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    await state.clear()
    
    # Получаем количество шаблонов
    templates = await db.get_templates()
    
    await callback.message.edit_text(
        "📁 <b>Шаблоны рассылок</b>\n\n"
        f"Сохранённых шаблонов: {len(templates)}\n\n"
        "Шаблоны позволяют сохранять тексты рассылок для повторного использования.",
        reply_markup=get_template_menu_keyboard(),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@router.callback_query(TemplateMenuCallback.filter(F.action == "create"))
async def template_start_create(callback: CallbackQuery, state: FSMContext):
    """Начать создание шаблона"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    await state.set_state(TemplateState.waiting_for_content)
    
    await callback.message.edit_text(
        "📝 <b>Создание шаблона</b>\n\n"
        "Отправьте текст шаблона рассылки.\n\n"
        "💡 <i>Можете использовать HTML-форматирование</i>",
        parse_mode=ParseMode.HTML
    )
    
    await callback.message.answer(
        "❌ Для отмены нажмите кнопку ниже",
        reply_markup=get_cancel_keyboard()
    )
    await callback.answer()


@router.callback_query(TemplateMenuCallback.filter(F.action == "back"))
async def template_back_to_broadcast_menu(callback: CallbackQuery, state: FSMContext):
    """Вернуться в меню рассылок из шаблонов"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    await state.clear()
    await callback.message.edit_text(
        "📣 <b>Управление рассылками</b>\n\n"
        "Здесь вы можете создавать и управлять рассылками для пользователей.",
        reply_markup=get_broadcast_menu_keyboard(),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@router.message(F.text == "❌ Отмена", TemplateState.waiting_for_content)
@router.message(F.text == "❌ Отмена", TemplateState.waiting_for_name)
async def template_cancel(message: Message, state: FSMContext):
    """Отмена создания шаблона"""
    if not is_admin(message.from_user.username):
        return

    await state.clear()
    await message.answer(
        "❌ Создание шаблона отменено.",
        reply_markup=get_admin_main_menu()
    )
    await message.answer(
        "📁 <b>Шаблоны рассылок</b>",
        reply_markup=get_template_menu_keyboard(),
        parse_mode=ParseMode.HTML
    )


@router.message(TemplateState.waiting_for_content)
async def template_receive_content(message: Message, state: FSMContext):
    """Получение текста шаблона"""
    if not is_admin(message.from_user.username):
        return

    content = message.html_text
    await state.update_data(content=content)
    await state.set_state(TemplateState.waiting_for_name)
    
    await message.answer(
        "👁 <b>Превью шаблона:</b>\n\n"
        f"{content}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📌 <b>Отправьте название шаблона</b>\n"
        "(короткое название для удобного поиска)",
        parse_mode=ParseMode.HTML
    )


@router.message(TemplateState.waiting_for_name)
async def template_receive_name(message: Message, state: FSMContext):
    """Получение названия шаблона и сохранение"""
    if not is_admin(message.from_user.username):
        return

    name = message.text.strip()[:100]  # Ограничиваем длину
    data = await state.get_data()
    content = data.get('content', '')
    
    # Сохраняем шаблон
    template_id = await db.create_template(
        content=content,
        created_by=message.from_user.id,
        created_by_username=message.from_user.username,
        name=name
    )
    
    await state.clear()
    
    await message.answer(
        f"✅ <b>Шаблон сохранён!</b>\n\n"
        f"📌 Название: {name}\n"
        f"🆔 ID: {template_id}",
        reply_markup=get_admin_main_menu(),
        parse_mode=ParseMode.HTML
    )
    await message.answer(
        "📁 <b>Шаблоны рассылок</b>",
        reply_markup=get_template_menu_keyboard(),
        parse_mode=ParseMode.HTML
    )
    
    logger.info(f"Template {template_id} created by {message.from_user.username}")


@router.callback_query(TemplateSelectCallback.filter(F.action == "view"))
async def template_view_list_or_item(callback: CallbackQuery, callback_data: TemplateSelectCallback):
    """Показать список шаблонов или конкретный шаблон"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    template_id = callback_data.template_id
    page = callback_data.page
    
    if template_id == 0:
        # Показываем список с пагинацией
        templates = await db.get_templates()
        
        if not templates:
            await callback.answer("📭 Нет сохранённых шаблонов", show_alert=True)
            return
        
        await callback.message.edit_text(
            "📋 <b>Мои шаблоны</b>\n\n"
            f"Всего: {len(templates)}",
            reply_markup=get_template_list_keyboard(templates, page),
            parse_mode=ParseMode.HTML
        )
    else:
        # Показываем конкретный шаблон
        template = await db.get_template(template_id)
        
        if not template:
            await callback.answer("❌ Шаблон не найден", show_alert=True)
            return
        
        await callback.message.edit_text(
            f"📄 <b>Шаблон: {template.get('name', 'Без названия')}</b>\n\n"
            f"{template['content']}\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 Создал: @{template.get('created_by_username', 'unknown')}",
            reply_markup=get_template_view_keyboard(template_id),
            parse_mode=ParseMode.HTML
        )
    
    await callback.answer()


@router.callback_query(TemplateSelectCallback.filter(F.action == "use"))
async def template_use_for_broadcast(callback: CallbackQuery, callback_data: TemplateSelectCallback, state: FSMContext):
    """Использовать шаблон для обычной рассылки"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    template = await db.get_template(callback_data.template_id)
    
    if not template:
        await callback.answer("❌ Шаблон не найден", show_alert=True)
        return
    
    # Сохраняем текст в состояние и переходим к выбору аудитории
    await state.update_data(content=template['content'])
    
    await callback.message.edit_text(
        "👁 <b>Превью рассылки:</b>\n\n"
        f"{template['content']}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🎯 <b>Выберите аудиторию рассылки:</b>",
        reply_markup=get_broadcast_audience_keyboard(),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@router.callback_query(TemplateSelectCallback.filter(F.action == "use_auto"))
async def template_use_for_auto_broadcast(callback: CallbackQuery, callback_data: TemplateSelectCallback, state: FSMContext):
    """Использовать шаблон для авто-рассылки"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    template = await db.get_template(callback_data.template_id)
    
    if not template:
        await callback.answer("❌ Шаблон не найден", show_alert=True)
        return
    
    # Сохраняем текст в состояние и переходим к выбору триггера
    await state.update_data(content=template['content'])
    
    await callback.message.edit_text(
        "🤖 <b>Создание авто-рассылки</b>\n\n"
        f"📝 Текст:\n{template['content']}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🎯 <b>Выберите триггер:</b>\n"
        "Когда отправлять это сообщение?",
        reply_markup=get_auto_broadcast_trigger_keyboard(),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@router.callback_query(TemplateSelectCallback.filter(F.action == "delete"))
async def template_delete(callback: CallbackQuery, callback_data: TemplateSelectCallback):
    """Удалить шаблон"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    deleted = await db.delete_template(callback_data.template_id)
    
    if deleted:
        logger.info(f"Template {callback_data.template_id} deleted by {callback.from_user.username}")
        await callback.answer("✅ Шаблон удалён!", show_alert=True)
        
        # Показываем обновлённый список
        templates = await db.get_templates()
        
        if not templates:
            await callback.message.edit_text(
                "📁 <b>Шаблоны рассылок</b>\n\n"
                "📭 Нет сохранённых шаблонов.",
                reply_markup=get_template_menu_keyboard(),
                parse_mode=ParseMode.HTML
            )
        else:
            await callback.message.edit_text(
                "📋 <b>Мои шаблоны</b>\n\n"
                f"Всего: {len(templates)}",
                reply_markup=get_template_list_keyboard(templates),
                parse_mode=ParseMode.HTML
            )
    else:
        await callback.answer("❌ Не удалось удалить шаблон", show_alert=True)


# ==================== Auto-Broadcast Management ====================

@router.callback_query(AutoBroadcastMenuCallback.filter(F.action == "list"))
async def auto_broadcast_show_menu(callback: CallbackQuery, state: FSMContext):
    """Показать меню авто-рассылок"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    await state.clear()
    
    auto_broadcasts = await db.get_auto_broadcasts()
    active_count = len([ab for ab in auto_broadcasts if ab.get('is_active')])
    
    await callback.message.edit_text(
        "🤖 <b>Автоматические рассылки</b>\n\n"
        f"Всего: {len(auto_broadcasts)}\n"
        f"Активных: {active_count}\n\n"
        "Авто-рассылки отправляются автоматически когда пользователь совершает определённое действие "
        "(или НЕ совершает его в течение заданного времени).",
        reply_markup=get_auto_broadcast_menu_keyboard(),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@router.callback_query(AutoBroadcastMenuCallback.filter(F.action == "create"))
async def auto_broadcast_start_create(callback: CallbackQuery, state: FSMContext):
    """Начать создание авто-рассылки"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    await state.set_state(AutoBroadcastState.waiting_for_content)
    
    await callback.message.edit_text(
        "📝 <b>Создание авто-рассылки</b>\n\n"
        "Отправьте текст сообщения, которое будет отправляться автоматически.\n\n"
        "💡 <i>Можете использовать HTML-форматирование</i>",
        parse_mode=ParseMode.HTML
    )
    
    await callback.message.answer(
        "❌ Для отмены нажмите кнопку ниже",
        reply_markup=get_cancel_keyboard()
    )
    await callback.answer()


@router.callback_query(AutoBroadcastMenuCallback.filter(F.action == "back"))
async def auto_broadcast_back_to_menu(callback: CallbackQuery, state: FSMContext):
    """Вернуться в меню рассылок из авто-рассылок"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    await state.clear()
    await callback.message.edit_text(
        "📣 <b>Управление рассылками</b>\n\n"
        "Здесь вы можете создавать и управлять рассылками для пользователей.",
        reply_markup=get_broadcast_menu_keyboard(),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@router.message(F.text == "❌ Отмена", AutoBroadcastState.waiting_for_content)
async def auto_broadcast_cancel(message: Message, state: FSMContext):
    """Отмена создания авто-рассылки"""
    if not is_admin(message.from_user.username):
        return

    await state.clear()
    await message.answer(
        "❌ Создание авто-рассылки отменено.",
        reply_markup=get_admin_main_menu()
    )
    await message.answer(
        "🤖 <b>Автоматические рассылки</b>",
        reply_markup=get_auto_broadcast_menu_keyboard(),
        parse_mode=ParseMode.HTML
    )


@router.message(AutoBroadcastState.waiting_for_content)
async def auto_broadcast_receive_content(message: Message, state: FSMContext):
    """Получение текста авто-рассылки"""
    if not is_admin(message.from_user.username):
        return

    content = message.html_text
    await state.update_data(content=content)
    await state.set_state(None)
    
    await message.answer(
        "👁 <b>Превью авто-рассылки:</b>\n\n"
        f"{content}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🎯 <b>Выберите триггер:</b>\n"
        "Когда отправлять это сообщение?",
        reply_markup=get_auto_broadcast_trigger_keyboard(),
        parse_mode=ParseMode.HTML
    )


@router.callback_query(AutoBroadcastTriggerCallback.filter())
async def auto_broadcast_select_trigger(callback: CallbackQuery, callback_data: AutoBroadcastTriggerCallback, state: FSMContext):
    """Выбор триггера авто-рассылки"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    trigger = callback_data.trigger
    await state.update_data(trigger=trigger)
    
    trigger_name = get_trigger_display_name(trigger)
    data = await state.get_data()
    content = data.get('content', '')
    
    await callback.message.edit_text(
        "👁 <b>Превью авто-рассылки:</b>\n\n"
        f"{content}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🎯 <b>Триггер:</b> {trigger_name}\n\n"
        "⏰ <b>Выберите задержку:</b>\n"
        "Через сколько времени после триггера отправить?",
        reply_markup=get_auto_broadcast_delay_keyboard(),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@router.callback_query(AutoBroadcastDelayCallback.filter())
async def auto_broadcast_select_delay(callback: CallbackQuery, callback_data: AutoBroadcastDelayCallback, state: FSMContext):
    """Выбор задержки авто-рассылки"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    delay_hours = callback_data.hours
    await state.update_data(delay_hours=delay_hours)
    
    data = await state.get_data()
    content = data.get('content', '')
    trigger = data.get('trigger', '')
    
    trigger_name = get_trigger_display_name(trigger)
    
    # Форматируем задержку
    if delay_hours < 24:
        delay_str = f"{delay_hours} час." if delay_hours == 1 else f"{delay_hours} час."
    elif delay_hours == 24:
        delay_str = "24 часа (1 день)"
    elif delay_hours == 48:
        delay_str = "48 часов (2 дня)"
    else:
        delay_str = f"{delay_hours} часов ({delay_hours // 24} дня)"
    
    await callback.message.edit_text(
        "🚀 <b>ПОДТВЕРЖДЕНИЕ АВТО-РАССЫЛКИ</b>\n\n"
        f"📝 <b>Текст:</b>\n{content}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🎯 <b>Триггер:</b> {trigger_name}\n"
        f"⏰ <b>Задержка:</b> {delay_str}\n\n"
        "⚠️ <b>Проверьте всё внимательно!</b>\n"
        "После подтверждения авто-рассылка будет активирована.",
        reply_markup=get_auto_broadcast_confirm_keyboard(),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@router.callback_query(AutoBroadcastConfirmCallback.filter(F.action == "confirm"))
async def auto_broadcast_confirm(callback: CallbackQuery, state: FSMContext):
    """Подтверждение создания авто-рассылки"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    data = await state.get_data()
    content = data.get('content', '')
    trigger = data.get('trigger', '')
    delay_hours = data.get('delay_hours', 24)
    
    if not content or not trigger:
        await callback.answer("❌ Ошибка: данные утеряны", show_alert=True)
        return
    
    # Создаём авто-рассылку
    auto_id = await db.create_auto_broadcast(
        trigger_type=trigger,
        content=content,
        delay_hours=delay_hours,
        created_by=callback.from_user.id,
        created_by_username=callback.from_user.username
    )
    
    await state.clear()
    
    trigger_name = get_trigger_display_name(trigger)
    
    await callback.message.edit_text(
        "✅ <b>Авто-рассылка создана!</b>\n\n"
        f"🆔 ID: {auto_id}\n"
        f"🎯 Триггер: {trigger_name}\n"
        f"⏰ Задержка: {delay_hours} ч.\n"
        f"📊 Статус: 🟢 Активна\n\n"
        "Рассылка будет отправляться автоматически.",
        reply_markup=get_auto_broadcast_menu_keyboard(),
        parse_mode=ParseMode.HTML
    )
    
    logger.info(f"Auto-broadcast {auto_id} created by {callback.from_user.username}")
    await callback.answer("✅ Авто-рассылка создана!")


@router.callback_query(AutoBroadcastConfirmCallback.filter(F.action == "edit"))
async def auto_broadcast_edit(callback: CallbackQuery, state: FSMContext):
    """Редактирование текста авто-рассылки"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    await state.set_state(AutoBroadcastState.waiting_for_content)
    
    await callback.message.edit_text(
        "✏️ <b>Редактирование авто-рассылки</b>\n\n"
        "Отправьте новый текст.",
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@router.callback_query(AutoBroadcastConfirmCallback.filter(F.action == "cancel"))
async def auto_broadcast_cancel_create(callback: CallbackQuery, state: FSMContext):
    """Отмена создания авто-рассылки"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    await state.clear()
    
    await callback.message.edit_text(
        "❌ Создание авто-рассылки отменено.\n\n"
        "🤖 <b>Автоматические рассылки</b>",
        reply_markup=get_auto_broadcast_menu_keyboard(),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@router.callback_query(AutoBroadcastListCallback.filter(F.action == "view"))
async def auto_broadcast_view_list_or_item(callback: CallbackQuery, callback_data: AutoBroadcastListCallback):
    """Показать список авто-рассылок или конкретную"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    auto_id = callback_data.auto_id
    page = callback_data.page
    
    if auto_id == 0:
        # Показываем список
        auto_broadcasts = await db.get_auto_broadcasts()
        
        if not auto_broadcasts:
            await callback.answer("📭 Нет авто-рассылок", show_alert=True)
            return
        
        await callback.message.edit_text(
            "📋 <b>Активные авто-рассылки</b>\n\n"
            f"Всего: {len(auto_broadcasts)}",
            reply_markup=get_auto_broadcast_list_keyboard(auto_broadcasts, page),
            parse_mode=ParseMode.HTML
        )
    else:
        # Показываем конкретную авто-рассылку
        auto_bc = await db.get_auto_broadcast(auto_id)
        
        if not auto_bc:
            await callback.answer("❌ Авто-рассылка не найдена", show_alert=True)
            return
        
        trigger_name = get_trigger_display_name(auto_bc['trigger_type'])
        status = "🟢 Активна" if auto_bc['is_active'] else "🔴 Приостановлена"
        
        await callback.message.edit_text(
            f"🤖 <b>Авто-рассылка #{auto_id}</b>\n\n"
            f"📝 <b>Текст:</b>\n{auto_bc['content']}\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🎯 <b>Триггер:</b> {trigger_name}\n"
            f"⏰ <b>Задержка:</b> {auto_bc['delay_hours']} ч.\n"
            f"📊 <b>Статус:</b> {status}\n"
            f"📨 <b>Отправлено:</b> {auto_bc['sent_count']} раз\n"
            f"👤 <b>Создал:</b> @{auto_bc.get('created_by_username', 'unknown')}",
            reply_markup=get_auto_broadcast_view_keyboard(auto_id, auto_bc['is_active']),
            parse_mode=ParseMode.HTML
        )
    
    await callback.answer()


@router.callback_query(AutoBroadcastListCallback.filter(F.action == "toggle"))
async def auto_broadcast_toggle(callback: CallbackQuery, callback_data: AutoBroadcastListCallback):
    """Переключить активность авто-рассылки"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    auto_id = callback_data.auto_id
    toggled = await db.toggle_auto_broadcast(auto_id)
    
    if toggled:
        auto_bc = await db.get_auto_broadcast(auto_id)
        status = "активирована" if auto_bc['is_active'] else "приостановлена"
        logger.info(f"Auto-broadcast {auto_id} {status} by {callback.from_user.username}")
        await callback.answer(f"✅ Авто-рассылка {status}!", show_alert=True)
        
        # Обновляем отображение
        trigger_name = get_trigger_display_name(auto_bc['trigger_type'])
        status_emoji = "🟢 Активна" if auto_bc['is_active'] else "🔴 Приостановлена"
        
        await callback.message.edit_text(
            f"🤖 <b>Авто-рассылка #{auto_id}</b>\n\n"
            f"📝 <b>Текст:</b>\n{auto_bc['content']}\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🎯 <b>Триггер:</b> {trigger_name}\n"
            f"⏰ <b>Задержка:</b> {auto_bc['delay_hours']} ч.\n"
            f"📊 <b>Статус:</b> {status_emoji}\n"
            f"📨 <b>Отправлено:</b> {auto_bc['sent_count']} раз\n"
            f"👤 <b>Создал:</b> @{auto_bc.get('created_by_username', 'unknown')}",
            reply_markup=get_auto_broadcast_view_keyboard(auto_id, auto_bc['is_active']),
            parse_mode=ParseMode.HTML
        )
    else:
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(AutoBroadcastListCallback.filter(F.action == "delete"))
async def auto_broadcast_delete(callback: CallbackQuery, callback_data: AutoBroadcastListCallback):
    """Удалить авто-рассылку"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    auto_id = callback_data.auto_id
    deleted = await db.delete_auto_broadcast(auto_id)
    
    if deleted:
        logger.info(f"Auto-broadcast {auto_id} deleted by {callback.from_user.username}")
        await callback.answer("✅ Авто-рассылка удалена!", show_alert=True)
        
        # Показываем обновлённый список
        auto_broadcasts = await db.get_auto_broadcasts()
        
        if not auto_broadcasts:
            await callback.message.edit_text(
                "🤖 <b>Автоматические рассылки</b>\n\n"
                "📭 Нет авто-рассылок.",
                reply_markup=get_auto_broadcast_menu_keyboard(),
                parse_mode=ParseMode.HTML
            )
        else:
            await callback.message.edit_text(
                "📋 <b>Активные авто-рассылки</b>\n\n"
                f"Всего: {len(auto_broadcasts)}",
                reply_markup=get_auto_broadcast_list_keyboard(auto_broadcasts),
                parse_mode=ParseMode.HTML
            )
    else:
        await callback.answer("❌ Не удалось удалить", show_alert=True)
