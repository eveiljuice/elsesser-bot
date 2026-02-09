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
    AutoBroadcastListCallback,
    ChainMenuCallback,
    ChainListCallback,
    ChainEditCallback,
    ChainStepCallback,
    ChainButtonActionCallback,
    ChainTriggerCallback,
    ChainAudienceCallback,
    UserManageMenuCallback,
    UserListCallback,
    UserActionCallback,
    SupportReplyCallback
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
    get_skip_keyboard,
    get_chain_menu_keyboard,
    get_chain_trigger_keyboard,
    get_chain_list_keyboard,
    get_chain_view_keyboard,
    get_chain_steps_keyboard,
    get_chain_step_view_keyboard,
    get_chain_button_action_keyboard,
    get_chain_step_buttons_keyboard,
    get_chain_button_edit_keyboard,
    get_chain_audience_keyboard,
    get_chain_confirm_send_keyboard,
    get_chain_step_goto_keyboard,
    get_user_management_menu,
    get_user_list_keyboard,
    get_user_view_keyboard,
    get_user_confirm_reset_keyboard
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


class ChainState(StatesGroup):
    """Состояния для создания/редактирования цепочки рассылок"""
    waiting_for_name = State()
    waiting_for_description = State()
    waiting_for_step_content = State()
    waiting_for_step_media = State()
    waiting_for_step_delay = State()
    waiting_for_button_text = State()
    waiting_for_button_value = State()
    waiting_for_goto_step = State()


class UserSearchState(StatesGroup):
    """Состояния для поиска пользователя"""
    waiting_for_query = State()


class SupportReplyState(StatesGroup):
    """Состояния для ответа модератора на вопрос пользователя"""
    waiting_for_reply = State()


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

    logger.info(
        f"Processing payment approval for user {user_id}, product {product_type}")

    # Обновляем статус оплаты пользователя в зависимости от типа продукта
    if product_type == 'fmd':
        await db.set_fmd_payment_status(user_id, True)
    elif product_type == 'bundle':
        await db.set_bundle_payment_status(user_id, True)
    elif product_type == 'dry':
        await db.set_dry_payment_status(user_id, True)
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
        elif product_type == 'bundle':
            # Комплект: Рационы + FMD
            await bot.send_message(
                chat_id=user_id,
                text=(
                    "🎉 <b>Оплата комплекта подтверждена!</b>\n\n"
                    "Теперь у тебя есть полный доступ:\n"
                    "• 🍽 Рационы питания на 14 дней\n"
                    "• 🥗 FMD Протокол на 5 дней\n\n"
                    "Нажми «🍽 Выбрать рацион» чтобы начать!"
                ),
                reply_markup=get_main_menu(),
                parse_mode=ParseMode.HTML
            )

            # Для комплекта тоже предлагаем калькулятор
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
        elif product_type == 'dry':
            # Сушка
            await bot.send_message(
                chat_id=user_id,
                text=(
                    "🎉 <b>Оплата Сушки подтверждена!</b>\n\n"
                    "Теперь у тебя есть доступ к 14-дневной программе Сушка!\n\n"
                    "🔥 Нажми «🍽 Выбрать рацион» → «Сушка» чтобы начать."
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
        product_names = {
            'fmd': "FMD Протокола",
            'bundle': "комплекта",
            'dry': "Сушки",
            'main': "рациона"
        }
        product_name = product_names.get(product_type, "рациона")
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

    # Очищаем медиа из состояния (если были добавлены ранее)
    await state.update_data(media_type=None, media_file_id=None)

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
        # Берём фото максимального размера
        media_file_id = message.photo[-1].file_id
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

    # Очищаем кнопки из состояния (если были добавлены ранее)
    await state.update_data(buttons=None)

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

    # Валидация контента перед созданием рассылки
    from followup import validate_broadcast_content
    is_valid, error_msg = validate_broadcast_content(
        content, media_type, media_file_id, buttons)
    if not is_valid:
        await callback.message.answer(
            error_msg,
            parse_mode=ParseMode.HTML
        )
        await callback.answer("❌ Исправьте ошибки", show_alert=True)
        return

    # Конвертируем в UTC для хранения в БД
    if isinstance(scheduled_at, datetime) and scheduled_at.tzinfo:
        scheduled_at_utc = scheduled_at.astimezone(
            ZoneInfo("UTC")).replace(tzinfo=None)
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

    logger.info(
        f"Broadcast {broadcast_id} created by {callback.from_user.username}")
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
        dt_ekb = dt.replace(tzinfo=ZoneInfo(
            "UTC")).astimezone(YEKATERINBURG_TZ)
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
        logger.info(
            f"Broadcast {broadcast_id} cancelled by {callback.from_user.username}")
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
    """Показать меню шаблонов или список шаблонов"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    await state.clear()

    # Получаем шаблоны
    templates = await db.get_templates()

    if not templates:
        # Если шаблонов нет, показываем меню
        await callback.message.edit_text(
            "📁 <b>Шаблоны рассылок</b>\n\n"
            "📭 Нет сохранённых шаблонов.\n\n"
            "Шаблоны позволяют сохранять тексты рассылок для повторного использования.",
            reply_markup=get_template_menu_keyboard(),
            parse_mode=ParseMode.HTML
        )
    else:
        # Если есть шаблоны, показываем список
        await callback.message.edit_text(
            "📋 <b>Мои шаблоны</b>\n\n"
            f"Всего: {len(templates)}",
            reply_markup=get_template_list_keyboard(templates),
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

    # Спрашиваем про медиа
    await state.set_state(TemplateState.waiting_for_media)
    await message.answer(
        "📸 <b>Добавление медиа (опционально)</b>\n\n"
        "Отправьте фото или видео, которое хотите добавить к шаблону.\n\n"
        "Или нажмите <b>Пропустить</b>, если медиа не нужно.",
        reply_markup=get_skip_keyboard(),
        parse_mode=ParseMode.HTML
    )


@router.message(TemplateState.waiting_for_media, F.text == "⏭ Пропустить")
async def template_skip_media(message: Message, state: FSMContext):
    """Пропуск добавления медиа для шаблона"""
    if not is_admin(message.from_user.username):
        return

    # Переходим к кнопкам
    await state.set_state(TemplateState.waiting_for_buttons)
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


@router.message(TemplateState.waiting_for_media, F.photo | F.video)
async def template_receive_media(message: Message, state: FSMContext):
    """Получение медиа для шаблона"""
    if not is_admin(message.from_user.username):
        return

    # Определяем тип медиа и file_id
    if message.photo:
        media_type = 'photo'
        media_file_id = message.photo[-1].file_id
    elif message.video:
        media_type = 'video'
        media_file_id = message.video.file_id
    else:
        await message.answer("❌ Пожалуйста, отправьте фото или видео.")
        return

    # Сохраняем медиа в состояние
    await state.update_data(media_type=media_type, media_file_id=media_file_id)

    # Переходим к кнопкам
    await state.set_state(TemplateState.waiting_for_buttons)
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


@router.message(TemplateState.waiting_for_buttons, F.text == "⏭ Пропустить")
async def template_skip_buttons(message: Message, state: FSMContext):
    """Пропуск добавления кнопок для шаблона"""
    if not is_admin(message.from_user.username):
        return

    # Переходим к названию
    await state.set_state(TemplateState.waiting_for_name)
    await message.answer(
        "📌 <b>Отправьте название шаблона</b>\n"
        "(короткое название для удобного поиска)",
        parse_mode=ParseMode.HTML
    )


@router.message(TemplateState.waiting_for_buttons, F.text)
async def template_receive_buttons(message: Message, state: FSMContext):
    """Получение кнопок для шаблона"""
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

    # Переходим к названию
    await state.set_state(TemplateState.waiting_for_name)
    await message.answer(
        f"✅ Кнопки добавлены: {len(buttons_data)} шт.\n\n"
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
    media_type = data.get('media_type')
    media_file_id = data.get('media_file_id')
    buttons = data.get('buttons')

    # Сохраняем шаблон
    template_id = await db.create_template(
        content=content,
        created_by=message.from_user.id,
        created_by_username=message.from_user.username,
        name=name,
        media_type=media_type,
        media_file_id=media_file_id,
        buttons=buttons
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

    logger.info(
        f"Template {template_id} created by {message.from_user.username}")


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
        logger.info(
            f"Template {callback_data.template_id} deleted by {callback.from_user.username}")
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

    # Спрашиваем про медиа
    await state.set_state(AutoBroadcastState.waiting_for_media)
    await message.answer(
        "📸 <b>Добавление медиа (опционально)</b>\n\n"
        "Отправьте фото или видео, которое хотите добавить к авто-рассылке.\n\n"
        "Или нажмите <b>Пропустить</b>, если медиа не нужно.",
        reply_markup=get_skip_keyboard(),
        parse_mode=ParseMode.HTML
    )


@router.message(AutoBroadcastState.waiting_for_media, F.text == "⏭ Пропустить")
async def auto_broadcast_skip_media(message: Message, state: FSMContext):
    """Пропуск добавления медиа для авто-рассылки"""
    if not is_admin(message.from_user.username):
        return

    # Очищаем медиа из состояния (если были добавлены ранее)
    await state.update_data(media_type=None, media_file_id=None)

    # Переходим к кнопкам
    await state.set_state(AutoBroadcastState.waiting_for_buttons)
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


@router.message(AutoBroadcastState.waiting_for_media, F.photo | F.video)
async def auto_broadcast_receive_media(message: Message, state: FSMContext):
    """Получение медиа для авто-рассылки"""
    if not is_admin(message.from_user.username):
        return

    # Определяем тип медиа и file_id
    if message.photo:
        media_type = 'photo'
        media_file_id = message.photo[-1].file_id
    elif message.video:
        media_type = 'video'
        media_file_id = message.video.file_id
    else:
        await message.answer("❌ Пожалуйста, отправьте фото или видео.")
        return

    # Сохраняем медиа в состояние
    await state.update_data(media_type=media_type, media_file_id=media_file_id)

    # Переходим к кнопкам
    await state.set_state(AutoBroadcastState.waiting_for_buttons)
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


@router.message(AutoBroadcastState.waiting_for_buttons, F.text == "⏭ Пропустить")
async def auto_broadcast_skip_buttons(message: Message, state: FSMContext):
    """Пропуск добавления кнопок для авто-рассылки"""
    if not is_admin(message.from_user.username):
        return

    # Очищаем кнопки из состояния (если были добавлены ранее)
    await state.update_data(buttons=None)

    # Получаем данные для превью
    data = await state.get_data()
    content = data.get('content', '')

    # Переходим к выбору триггера
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


@router.message(AutoBroadcastState.waiting_for_buttons, F.text)
async def auto_broadcast_receive_buttons(message: Message, state: FSMContext):
    """Получение кнопок для авто-рассылки"""
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

    # Переходим к выбору триггера
    await state.set_state(None)
    await message.answer(
        f"✅ Кнопки добавлены: {len(buttons_data)} шт.\n\n"
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
    media_type = data.get('media_type')
    media_file_id = data.get('media_file_id')
    buttons = data.get('buttons')

    if not content or not trigger:
        await callback.answer("❌ Ошибка: данные утеряны", show_alert=True)
        return

    # Валидация контента перед созданием авто-рассылки
    from followup import validate_broadcast_content
    is_valid, error_msg = validate_broadcast_content(
        content, media_type, media_file_id, buttons)
    if not is_valid:
        await callback.message.answer(
            error_msg,
            parse_mode=ParseMode.HTML
        )
        await callback.answer("❌ Исправьте ошибки", show_alert=True)
        return

    # Создаём авто-рассылку
    auto_id = await db.create_auto_broadcast(
        trigger_type=trigger,
        content=content,
        delay_hours=delay_hours,
        created_by=callback.from_user.id,
        created_by_username=callback.from_user.username,
        media_type=media_type,
        media_file_id=media_file_id,
        buttons=buttons
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

    logger.info(
        f"Auto-broadcast {auto_id} created by {callback.from_user.username}")
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
            reply_markup=get_auto_broadcast_list_keyboard(
                auto_broadcasts, page),
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
            reply_markup=get_auto_broadcast_view_keyboard(
                auto_id, auto_bc['is_active']),
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
        logger.info(
            f"Auto-broadcast {auto_id} {status} by {callback.from_user.username}")
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
            reply_markup=get_auto_broadcast_view_keyboard(
                auto_id, auto_bc['is_active']),
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
        logger.info(
            f"Auto-broadcast {auto_id} deleted by {callback.from_user.username}")
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


# ==================== Broadcast Chain Management ====================

def get_chain_trigger_name(trigger: str) -> str:
    """Получить отображаемое название триггера цепочки"""
    names = {
        'manual': '✋ Ручной запуск',
        'subscription_end': '⏰ Конец подписки',
        'payment_approved': '✅ После оплаты',
        'custom': '⚙️ Кастомный'
    }
    return names.get(trigger, trigger)


@router.callback_query(ChainMenuCallback.filter(F.action == "list"))
async def chain_show_menu(callback: CallbackQuery, state: FSMContext):
    """Показать меню цепочек рассылок"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    await state.clear()

    await callback.message.edit_text(
        "🔗 <b>Цепочки рассылок</b>\n\n"
        "Цепочки — это последовательность сообщений с кнопками.\n"
        "Каждая кнопка может переводить на следующий шаг, "
        "запускать оплату или останавливать цепочку.",
        reply_markup=get_chain_menu_keyboard(),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@router.callback_query(ChainMenuCallback.filter(F.action == "create"))
async def chain_start_create(callback: CallbackQuery, state: FSMContext):
    """Начать создание цепочки"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    await state.set_state(ChainState.waiting_for_name)

    await callback.message.edit_text(
        "📝 <b>Создание цепочки рассылок</b>\n\n"
        "Отправьте название цепочки.\n"
        "Например: <code>Воронка продаж после оплаты</code>",
        parse_mode=ParseMode.HTML
    )

    await callback.message.answer(
        "❌ Для отмены нажмите кнопку ниже",
        reply_markup=get_cancel_keyboard()
    )
    await callback.answer()


@router.callback_query(ChainMenuCallback.filter(F.action == "back"))
async def chain_back_to_broadcast_menu(callback: CallbackQuery, state: FSMContext):
    """Вернуться в меню рассылок из цепочек"""
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


@router.message(F.text == "❌ Отмена", ChainState.waiting_for_name)
@router.message(F.text == "❌ Отмена", ChainState.waiting_for_description)
@router.message(F.text == "❌ Отмена", ChainState.waiting_for_step_content)
@router.message(F.text == "❌ Отмена", ChainState.waiting_for_step_delay)
@router.message(F.text == "❌ Отмена", ChainState.waiting_for_button_text)
@router.message(F.text == "❌ Отмена", ChainState.waiting_for_button_value)
async def chain_cancel(message: Message, state: FSMContext):
    """Отмена создания/редактирования цепочки"""
    if not is_admin(message.from_user.username):
        return

    await state.clear()
    await message.answer(
        "❌ Операция отменена.",
        reply_markup=get_admin_main_menu()
    )
    await message.answer(
        "🔗 <b>Цепочки рассылок</b>",
        reply_markup=get_chain_menu_keyboard(),
        parse_mode=ParseMode.HTML
    )


@router.message(ChainState.waiting_for_name)
async def chain_receive_name(message: Message, state: FSMContext):
    """Получение названия цепочки"""
    if not is_admin(message.from_user.username):
        return

    name = message.text.strip()[:100]
    await state.update_data(chain_name=name)

    await state.set_state(ChainState.waiting_for_description)
    await message.answer(
        f"✅ Название: <b>{name}</b>\n\n"
        "📋 Теперь отправьте описание цепочки (опционально).\n"
        "Или нажмите <b>Пропустить</b>.",
        reply_markup=get_skip_keyboard(),
        parse_mode=ParseMode.HTML
    )


@router.message(ChainState.waiting_for_description, F.text == "⏭ Пропустить")
async def chain_skip_description(message: Message, state: FSMContext):
    """Пропуск описания цепочки"""
    if not is_admin(message.from_user.username):
        return

    await state.update_data(chain_description=None)

    # Показываем выбор триггера
    await state.set_state(None)
    await message.answer(
        "🎯 <b>Выберите триггер запуска цепочки</b>\n\n"
        "Когда пользователь должен начать получать эту цепочку?",
        reply_markup=get_chain_trigger_keyboard(),
        parse_mode=ParseMode.HTML
    )


@router.message(ChainState.waiting_for_description)
async def chain_receive_description(message: Message, state: FSMContext):
    """Получение описания цепочки"""
    if not is_admin(message.from_user.username):
        return

    description = message.text.strip()[:500]
    await state.update_data(chain_description=description)

    # Показываем выбор триггера
    await state.set_state(None)
    await message.answer(
        "🎯 <b>Выберите триггер запуска цепочки</b>\n\n"
        "Когда пользователь должен начать получать эту цепочку?",
        reply_markup=get_chain_trigger_keyboard(),
        parse_mode=ParseMode.HTML
    )


@router.callback_query(ChainTriggerCallback.filter())
async def chain_select_trigger(callback: CallbackQuery, callback_data: ChainTriggerCallback, state: FSMContext):
    """Выбор триггера и создание цепочки"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    trigger = callback_data.trigger
    data = await state.get_data()
    name = data.get('chain_name', 'Без названия')
    description = data.get('chain_description')

    # Создаём цепочку
    chain_id = await db.create_chain(
        name=name,
        trigger_type=trigger,
        created_by=callback.from_user.id,
        created_by_username=callback.from_user.username,
        description=description
    )

    await state.clear()

    trigger_name = get_chain_trigger_name(trigger)

    await callback.message.edit_text(
        f"✅ <b>Цепочка создана!</b>\n\n"
        f"📌 Название: {name}\n"
        f"🎯 Триггер: {trigger_name}\n"
        f"🆔 ID: {chain_id}\n\n"
        "Теперь добавьте шаги в цепочку.",
        reply_markup=get_chain_view_keyboard(chain_id, True, 0),
        parse_mode=ParseMode.HTML
    )

    await callback.message.answer(
        "Вернитесь к админ-меню:",
        reply_markup=get_admin_main_menu()
    )

    logger.info(f"Chain {chain_id} created by {callback.from_user.username}")
    await callback.answer("✅ Цепочка создана!")


@router.callback_query(ChainListCallback.filter(F.action == "view"))
async def chain_view_list_or_item(callback: CallbackQuery, callback_data: ChainListCallback, state: FSMContext):
    """Показать список цепочек или конкретную цепочку"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    chain_id = callback_data.chain_id
    page = callback_data.page

    if chain_id == 0:
        # Показываем список цепочек
        chains = await db.get_all_chains()

        if not chains:
            await callback.message.edit_text(
                "🔗 <b>Цепочки рассылок</b>\n\n"
                "📭 Нет созданных цепочек.",
                reply_markup=get_chain_menu_keyboard(),
                parse_mode=ParseMode.HTML
            )
        else:
            await callback.message.edit_text(
                "📋 <b>Мои цепочки</b>\n\n"
                f"Всего: {len(chains)}",
                reply_markup=get_chain_list_keyboard(chains, page),
                parse_mode=ParseMode.HTML
            )
    else:
        # Показываем конкретную цепочку
        chain = await db.get_chain(chain_id)

        if not chain:
            await callback.answer("❌ Цепочка не найдена", show_alert=True)
            return

        steps_count = await db.get_chain_steps_count(chain_id)
        stats = await db.get_chain_stats(chain_id)
        trigger_name = get_chain_trigger_name(chain['trigger_type'])
        status = "🟢 Активна" if chain['is_active'] else "🔴 Приостановлена"

        await callback.message.edit_text(
            f"🔗 <b>Цепочка: {chain['name']}</b>\n\n"
            f"{chain.get('description', '') or ''}\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🎯 <b>Триггер:</b> {trigger_name}\n"
            f"📊 <b>Статус:</b> {status}\n"
            f"📝 <b>Шагов:</b> {steps_count}\n\n"
            f"📈 <b>Статистика:</b>\n"
            f"├ Запустили: {stats['total_started']}\n"
            f"├ Активных: {stats['active']}\n"
            f"├ Завершили: {stats['completed']}\n"
            f"├ Остановили: {stats['stopped']}\n"
            f"└ Сообщений: {stats['messages_sent']}\n\n"
            f"👤 <b>Создал:</b> @{chain.get('created_by_username', 'unknown')}",
            reply_markup=get_chain_view_keyboard(
                chain_id, chain['is_active'], steps_count),
            parse_mode=ParseMode.HTML
        )

    await callback.answer()


@router.callback_query(ChainListCallback.filter(F.action == "toggle"))
async def chain_toggle(callback: CallbackQuery, callback_data: ChainListCallback):
    """Переключить активность цепочки"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    chain_id = callback_data.chain_id
    toggled = await db.toggle_chain_active(chain_id)

    if toggled:
        chain = await db.get_chain(chain_id)
        status = "активирована" if chain['is_active'] else "приостановлена"
        logger.info(
            f"Chain {chain_id} {status} by {callback.from_user.username}")
        await callback.answer(f"✅ Цепочка {status}!", show_alert=True)

        # Обновляем отображение
        steps_count = await db.get_chain_steps_count(chain_id)
        stats = await db.get_chain_stats(chain_id)
        trigger_name = get_chain_trigger_name(chain['trigger_type'])
        status_emoji = "🟢 Активна" if chain['is_active'] else "🔴 Приостановлена"

        await callback.message.edit_text(
            f"🔗 <b>Цепочка: {chain['name']}</b>\n\n"
            f"{chain.get('description', '') or ''}\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🎯 <b>Триггер:</b> {trigger_name}\n"
            f"📊 <b>Статус:</b> {status_emoji}\n"
            f"📝 <b>Шагов:</b> {steps_count}\n\n"
            f"📈 <b>Статистика:</b>\n"
            f"├ Запустили: {stats['total_started']}\n"
            f"├ Активных: {stats['active']}\n"
            f"├ Завершили: {stats['completed']}\n"
            f"├ Остановили: {stats['stopped']}\n"
            f"└ Сообщений: {stats['messages_sent']}\n\n"
            f"👤 <b>Создал:</b> @{chain.get('created_by_username', 'unknown')}",
            reply_markup=get_chain_view_keyboard(
                chain_id, chain['is_active'], steps_count),
            parse_mode=ParseMode.HTML
        )
    else:
        await callback.answer("❌ Ошибка", show_alert=True)


@router.callback_query(ChainListCallback.filter(F.action == "delete"))
async def chain_delete(callback: CallbackQuery, callback_data: ChainListCallback):
    """Удалить цепочку"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    chain_id = callback_data.chain_id
    deleted = await db.delete_chain(chain_id)

    if deleted:
        logger.info(
            f"Chain {chain_id} deleted by {callback.from_user.username}")
        await callback.answer("✅ Цепочка удалена!", show_alert=True)

        # Показываем обновлённый список
        chains = await db.get_all_chains()

        if not chains:
            await callback.message.edit_text(
                "🔗 <b>Цепочки рассылок</b>\n\n"
                "📭 Нет созданных цепочек.",
                reply_markup=get_chain_menu_keyboard(),
                parse_mode=ParseMode.HTML
            )
        else:
            await callback.message.edit_text(
                "📋 <b>Мои цепочки</b>\n\n"
                f"Всего: {len(chains)}",
                reply_markup=get_chain_list_keyboard(chains),
                parse_mode=ParseMode.HTML
            )
    else:
        await callback.answer("❌ Не удалось удалить", show_alert=True)


# ==================== Chain Steps Management ====================

@router.callback_query(ChainEditCallback.filter(F.action == "view_steps"))
async def chain_view_steps(callback: CallbackQuery, callback_data: ChainEditCallback):
    """Показать шаги цепочки"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    chain_id = callback_data.chain_id
    chain = await db.get_chain(chain_id)
    steps = await db.get_chain_steps(chain_id)

    if not chain:
        await callback.answer("❌ Цепочка не найдена", show_alert=True)
        return

    if not steps:
        await callback.message.edit_text(
            f"📝 <b>Шаги цепочки: {chain['name']}</b>\n\n"
            "📭 Пока нет шагов. Добавьте первый шаг!",
            reply_markup=get_chain_steps_keyboard(chain_id, []),
            parse_mode=ParseMode.HTML
        )
    else:
        await callback.message.edit_text(
            f"📝 <b>Шаги цепочки: {chain['name']}</b>\n\n"
            f"Всего шагов: {len(steps)}",
            reply_markup=get_chain_steps_keyboard(chain_id, steps),
            parse_mode=ParseMode.HTML
        )

    await callback.answer()


@router.callback_query(ChainEditCallback.filter(F.action == "add_step"))
async def chain_add_step_start(callback: CallbackQuery, callback_data: ChainEditCallback, state: FSMContext):
    """Начать добавление шага"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    chain_id = callback_data.chain_id
    steps_count = await db.get_chain_steps_count(chain_id)
    next_order = steps_count + 1

    await state.update_data(chain_id=chain_id, step_order=next_order)
    await state.set_state(ChainState.waiting_for_step_content)

    await callback.message.edit_text(
        f"📌 <b>Добавление шага #{next_order}</b>\n\n"
        "Отправьте текст сообщения для этого шага.\n\n"
        "💡 <i>Можете использовать HTML-форматирование</i>",
        parse_mode=ParseMode.HTML
    )

    await callback.message.answer(
        "❌ Для отмены нажмите кнопку ниже",
        reply_markup=get_cancel_keyboard()
    )
    await callback.answer()


@router.message(ChainState.waiting_for_step_content)
async def chain_receive_step_content(message: Message, state: FSMContext):
    """Получение текста шага"""
    if not is_admin(message.from_user.username):
        return

    content = message.html_text
    await state.update_data(step_content=content)

    # Спрашиваем про медиа
    await state.set_state(ChainState.waiting_for_step_media)
    await message.answer(
        "📸 <b>Добавление медиа (опционально)</b>\n\n"
        "Отправьте фото или видео для этого шага.\n"
        "Или нажмите <b>Пропустить</b>.",
        reply_markup=get_skip_keyboard(),
        parse_mode=ParseMode.HTML
    )


@router.message(ChainState.waiting_for_step_media, F.text == "⏭ Пропустить")
async def chain_skip_step_media(message: Message, state: FSMContext):
    """Пропуск медиа для шага"""
    if not is_admin(message.from_user.username):
        return

    await state.update_data(step_media_type=None, step_media_file_id=None)

    # Спрашиваем про задержку
    await state.set_state(ChainState.waiting_for_step_delay)
    await message.answer(
        "⏰ <b>Задержка перед отправкой</b>\n\n"
        "Через сколько часов после предыдущего шага отправить это сообщение?\n\n"
        "Отправьте число (0 для немедленной отправки).\n"
        "Например: <code>24</code> для отправки через сутки.",
        parse_mode=ParseMode.HTML
    )


@router.message(ChainState.waiting_for_step_media, F.photo | F.video)
async def chain_receive_step_media(message: Message, state: FSMContext):
    """Получение медиа для шага"""
    if not is_admin(message.from_user.username):
        return

    if message.photo:
        media_type = 'photo'
        media_file_id = message.photo[-1].file_id
    elif message.video:
        media_type = 'video'
        media_file_id = message.video.file_id
    else:
        await message.answer("❌ Пожалуйста, отправьте фото или видео.")
        return

    await state.update_data(step_media_type=media_type, step_media_file_id=media_file_id)

    # Спрашиваем про задержку
    await state.set_state(ChainState.waiting_for_step_delay)
    await message.answer(
        "✅ Медиа добавлено!\n\n"
        "⏰ <b>Задержка перед отправкой</b>\n\n"
        "Через сколько часов после предыдущего шага отправить это сообщение?\n\n"
        "Отправьте число (0 для немедленной отправки).\n"
        "Например: <code>24</code> для отправки через сутки.",
        parse_mode=ParseMode.HTML
    )


@router.message(ChainState.waiting_for_step_delay)
async def chain_receive_step_delay(message: Message, state: FSMContext):
    """Получение задержки и создание шага"""
    if not is_admin(message.from_user.username):
        return

    try:
        delay_hours = int(message.text.strip())
        if delay_hours < 0:
            delay_hours = 0
    except ValueError:
        await message.answer(
            "❌ Введите число.\n"
            "Например: <code>0</code> или <code>24</code>",
            parse_mode=ParseMode.HTML
        )
        return

    data = await state.get_data()
    chain_id = data.get('chain_id')
    step_order = data.get('step_order', 1)
    content = data.get('step_content', '')
    media_type = data.get('step_media_type')
    media_file_id = data.get('step_media_file_id')

    # Создаём шаг
    step_id = await db.add_chain_step(
        chain_id=chain_id,
        step_order=step_order,
        content=content,
        media_type=media_type,
        media_file_id=media_file_id,
        delay_hours=delay_hours
    )

    await state.clear()

    delay_str = f"+{delay_hours}ч" if delay_hours > 0 else "сразу"

    await message.answer(
        f"✅ <b>Шаг #{step_order} добавлен!</b>\n\n"
        f"⏰ Задержка: {delay_str}\n\n"
        "Теперь добавьте кнопки к этому шагу.",
        reply_markup=get_admin_main_menu(),
        parse_mode=ParseMode.HTML
    )

    # Показываем шаг
    buttons = await db.get_step_buttons(step_id)
    await message.answer(
        f"📌 <b>Шаг #{step_order}</b>\n\n"
        f"{content}\n\n"
        f"⏰ Задержка: {delay_str}",
        reply_markup=get_chain_step_view_keyboard(step_id, chain_id, buttons),
        parse_mode=ParseMode.HTML
    )

    logger.info(
        f"Chain step {step_id} added to chain {chain_id} by {message.from_user.username}")


@router.callback_query(ChainStepCallback.filter(F.action == "view"))
async def chain_step_view(callback: CallbackQuery, callback_data: ChainStepCallback):
    """Просмотр шага цепочки"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    step_id = callback_data.step_id
    step = await db.get_chain_step(step_id)

    if not step:
        await callback.answer("❌ Шаг не найден", show_alert=True)
        return

    buttons = await db.get_step_buttons(step_id)
    delay_str = f"+{step['delay_hours']}ч" if step['delay_hours'] > 0 else "сразу"

    await callback.message.edit_text(
        f"📌 <b>Шаг #{step['step_order']}</b>\n\n"
        f"{step['content']}\n\n"
        f"⏰ Задержка: {delay_str}\n"
        f"🔘 Кнопок: {len(buttons)}",
        reply_markup=get_chain_step_view_keyboard(
            step_id, step['chain_id'], buttons),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@router.callback_query(ChainStepCallback.filter(F.action == "view_buttons"))
async def chain_step_view_buttons(callback: CallbackQuery, callback_data: ChainStepCallback):
    """Просмотр кнопок шага"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    step_id = callback_data.step_id
    step = await db.get_chain_step(step_id)
    buttons = await db.get_step_buttons(step_id)

    if not step:
        await callback.answer("❌ Шаг не найден", show_alert=True)
        return

    await callback.message.edit_text(
        f"🔘 <b>Кнопки шага #{step['step_order']}</b>\n\n"
        f"Всего: {len(buttons)}",
        reply_markup=get_chain_step_buttons_keyboard(step_id, buttons),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@router.callback_query(ChainEditCallback.filter(F.action == "delete_step"))
async def chain_delete_step(callback: CallbackQuery, callback_data: ChainEditCallback):
    """Удалить шаг цепочки"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    step_id = callback_data.step_id
    chain_id = callback_data.chain_id

    deleted = await db.delete_chain_step(step_id)

    if deleted:
        logger.info(
            f"Chain step {step_id} deleted by {callback.from_user.username}")
        await callback.answer("✅ Шаг удалён!", show_alert=True)

        # Показываем обновлённый список шагов
        chain = await db.get_chain(chain_id)
        steps = await db.get_chain_steps(chain_id)

        if not steps:
            await callback.message.edit_text(
                f"📝 <b>Шаги цепочки: {chain['name']}</b>\n\n"
                "📭 Пока нет шагов. Добавьте первый шаг!",
                reply_markup=get_chain_steps_keyboard(chain_id, []),
                parse_mode=ParseMode.HTML
            )
        else:
            await callback.message.edit_text(
                f"📝 <b>Шаги цепочки: {chain['name']}</b>\n\n"
                f"Всего шагов: {len(steps)}",
                reply_markup=get_chain_steps_keyboard(chain_id, steps),
                parse_mode=ParseMode.HTML
            )
    else:
        await callback.answer("❌ Не удалось удалить", show_alert=True)


# ==================== Chain Button Management ====================

@router.callback_query(ChainStepCallback.filter(F.action == "add_button"))
async def chain_add_button_start(callback: CallbackQuery, callback_data: ChainStepCallback, state: FSMContext):
    """Начать добавление кнопки к шагу"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    step_id = callback_data.step_id
    await state.update_data(step_id=step_id)

    await callback.message.edit_text(
        "🔘 <b>Добавление кнопки</b>\n\n"
        "Выберите действие, которое выполнит кнопка:",
        reply_markup=get_chain_button_action_keyboard(step_id),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@router.callback_query(ChainButtonActionCallback.filter())
async def chain_select_button_action(callback: CallbackQuery, callback_data: ChainButtonActionCallback, state: FSMContext):
    """Выбор действия для кнопки"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    action_type = callback_data.action_type
    await state.update_data(button_action_type=action_type)

    # Для некоторых действий нужно дополнительное значение
    if action_type == 'goto_step':
        # Показываем список шагов для выбора
        data = await state.get_data()
        step_id = data.get('step_id')
        step = await db.get_chain_step(step_id)
        if step:
            steps = await db.get_chain_steps(step['chain_id'])
            await callback.message.edit_text(
                "🔀 <b>Выберите шаг для перехода</b>\n\n"
                "К какому шагу перейти при нажатии этой кнопки?",
                reply_markup=get_chain_step_goto_keyboard(
                    step['chain_id'], steps, step_id),
                parse_mode=ParseMode.HTML
            )
        await callback.answer()
        return

    elif action_type == 'url':
        await state.set_state(ChainState.waiting_for_button_value)
        await callback.message.edit_text(
            "🔗 <b>Введите URL</b>\n\n"
            "Отправьте ссылку, которая откроется при нажатии.\n"
            "Например: <code>https://example.com</code>",
            parse_mode=ParseMode.HTML
        )
        await callback.message.answer("❌ Для отмены:", reply_markup=get_cancel_keyboard())
        await callback.answer()
        return

    elif action_type == 'command':
        await state.set_state(ChainState.waiting_for_button_value)
        await callback.message.edit_text(
            "⌨️ <b>Введите команду</b>\n\n"
            "Отправьте команду бота.\n"
            "Например: <code>/menu</code> или <code>/start</code>",
            parse_mode=ParseMode.HTML
        )
        await callback.message.answer("❌ Для отмены:", reply_markup=get_cancel_keyboard())
        await callback.answer()
        return

    # Для остальных действий (next_step, stop_chain, payment_*) сразу спрашиваем текст кнопки
    await state.set_state(ChainState.waiting_for_button_text)
    await callback.message.edit_text(
        "📝 <b>Введите текст кнопки</b>\n\n"
        "Отправьте текст, который будет отображаться на кнопке.\n"
        "Например: <code>Продолжить</code> или <code>Оплатить</code>",
        parse_mode=ParseMode.HTML
    )
    await callback.message.answer("❌ Для отмены:", reply_markup=get_cancel_keyboard())
    await callback.answer()


@router.callback_query(ChainEditCallback.filter(F.action == "select_goto"))
async def chain_select_goto_step(callback: CallbackQuery, callback_data: ChainEditCallback, state: FSMContext):
    """Выбор шага для перехода"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    next_step_id = callback_data.step_id
    await state.update_data(next_step_id=next_step_id)

    # Спрашиваем текст кнопки
    await state.set_state(ChainState.waiting_for_button_text)
    await callback.message.edit_text(
        "📝 <b>Введите текст кнопки</b>\n\n"
        "Отправьте текст, который будет отображаться на кнопке.\n"
        "Например: <code>Продолжить</code>",
        parse_mode=ParseMode.HTML
    )
    await callback.message.answer("❌ Для отмены:", reply_markup=get_cancel_keyboard())
    await callback.answer()


@router.message(ChainState.waiting_for_button_value)
async def chain_receive_button_value(message: Message, state: FSMContext):
    """Получение значения для кнопки (URL или команда)"""
    if not is_admin(message.from_user.username):
        return

    value = message.text.strip()
    data = await state.get_data()
    action_type = data.get('button_action_type')

    # Валидация
    if action_type == 'url' and not (value.startswith('http://') or value.startswith('https://')):
        await message.answer(
            "❌ URL должен начинаться с http:// или https://\n"
            "Попробуйте ещё раз.",
            parse_mode=ParseMode.HTML
        )
        return

    if action_type == 'command' and not value.startswith('/'):
        await message.answer(
            "❌ Команда должна начинаться с /\n"
            "Например: <code>/menu</code>",
            parse_mode=ParseMode.HTML
        )
        return

    await state.update_data(button_action_value=value)

    # Спрашиваем текст кнопки
    await state.set_state(ChainState.waiting_for_button_text)
    await message.answer(
        "📝 <b>Введите текст кнопки</b>\n\n"
        "Отправьте текст, который будет отображаться на кнопке.",
        parse_mode=ParseMode.HTML
    )


@router.message(ChainState.waiting_for_button_text)
async def chain_receive_button_text(message: Message, state: FSMContext):
    """Получение текста кнопки и создание"""
    if not is_admin(message.from_user.username):
        return

    button_text = message.text.strip()[:50]  # Ограничение Telegram
    data = await state.get_data()

    step_id = data.get('step_id')
    action_type = data.get('button_action_type')
    action_value = data.get('button_action_value')
    next_step_id = data.get('next_step_id')

    # Получаем количество кнопок для определения порядка
    buttons = await db.get_step_buttons(step_id)
    button_order = len(buttons) + 1

    # Создаём кнопку
    button_id = await db.add_step_button(
        step_id=step_id,
        button_text=button_text,
        button_order=button_order,
        action_type=action_type,
        action_value=action_value,
        next_step_id=next_step_id
    )

    await state.clear()

    action_names = {
        'next_step': '➡️ Следующий шаг',
        'goto_step': '🔀 Переход к шагу',
        'url': '🔗 Ссылка',
        'command': '⌨️ Команда',
        'stop_chain': '⏹ Остановка',
        'payment_main': '💳 Оплата рациона',
        'payment_fmd': '🥗 Оплата FMD',
        'payment_bundle': '🎁 Оплата комплекта'
    }

    await message.answer(
        f"✅ <b>Кнопка добавлена!</b>\n\n"
        f"📝 Текст: {button_text}\n"
        f"⚙️ Действие: {action_names.get(action_type, action_type)}",
        reply_markup=get_admin_main_menu(),
        parse_mode=ParseMode.HTML
    )

    # Показываем шаг с кнопками
    step = await db.get_chain_step(step_id)
    buttons = await db.get_step_buttons(step_id)

    await message.answer(
        f"🔘 <b>Кнопки шага #{step['step_order']}</b>\n\n"
        f"Всего: {len(buttons)}",
        reply_markup=get_chain_step_buttons_keyboard(step_id, buttons),
        parse_mode=ParseMode.HTML
    )

    logger.info(
        f"Button {button_id} added to step {step_id} by {message.from_user.username}")


@router.callback_query(ChainStepCallback.filter(F.action == "delete_button"))
async def chain_delete_button(callback: CallbackQuery, callback_data: ChainStepCallback):
    """Удалить кнопку шага"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    button_id = callback_data.button_id
    step_id = callback_data.step_id

    deleted = await db.delete_step_button(button_id)

    if deleted:
        logger.info(
            f"Button {button_id} deleted by {callback.from_user.username}")
        await callback.answer("✅ Кнопка удалена!", show_alert=True)

        # Показываем обновлённый список кнопок
        step = await db.get_chain_step(step_id)
        buttons = await db.get_step_buttons(step_id)

        await callback.message.edit_text(
            f"🔘 <b>Кнопки шага #{step['step_order']}</b>\n\n"
            f"Всего: {len(buttons)}",
            reply_markup=get_chain_step_buttons_keyboard(step_id, buttons),
            parse_mode=ParseMode.HTML
        )
    else:
        await callback.answer("❌ Не удалось удалить", show_alert=True)


@router.callback_query(ChainStepCallback.filter(F.action == "edit_button"))
async def chain_edit_button(callback: CallbackQuery, callback_data: ChainStepCallback):
    """Редактирование кнопки (просмотр и удаление)"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    button_id = callback_data.button_id
    step_id = callback_data.step_id

    button = await db.get_step_button(button_id)
    if not button:
        await callback.answer("❌ Кнопка не найдена", show_alert=True)
        return

    action_names = {
        'next_step': '➡️ Следующий шаг',
        'goto_step': '🔀 Переход к шагу',
        'url': '🔗 Ссылка',
        'command': '⌨️ Команда',
        'stop_chain': '⏹ Остановка',
        'payment_main': '💳 Оплата рациона',
        'payment_fmd': '🥗 Оплата FMD',
        'payment_bundle': '🎁 Оплата комплекта'
    }

    action_value_str = ""
    if button.get('action_value'):
        action_value_str = f"\n📎 Значение: {button['action_value']}"
    if button.get('next_step_id'):
        action_value_str = f"\n📎 К шагу: #{button['next_step_id']}"

    await callback.message.edit_text(
        f"🔘 <b>Кнопка: {button['button_text']}</b>\n\n"
        f"⚙️ Действие: {action_names.get(button['action_type'], button['action_type'])}"
        f"{action_value_str}",
        reply_markup=get_chain_button_edit_keyboard(step_id, button_id),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


# ==================== Chain Send to Audience ====================

@router.callback_query(ChainEditCallback.filter(F.action == "start_send"))
async def chain_start_send(callback: CallbackQuery, callback_data: ChainEditCallback, state: FSMContext):
    """Начать отправку цепочки аудитории"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    chain_id = callback_data.chain_id
    chain = await db.get_chain(chain_id)
    steps = await db.get_chain_steps(chain_id)

    if not chain:
        await callback.answer("❌ Цепочка не найдена", show_alert=True)
        return

    if not steps:
        await callback.answer("❌ Добавьте хотя бы один шаг!", show_alert=True)
        return

    await state.update_data(send_chain_id=chain_id)

    await callback.message.edit_text(
        f"🚀 <b>Запуск цепочки: {chain['name']}</b>\n\n"
        f"📝 Шагов: {len(steps)}\n\n"
        "🎯 <b>Выберите аудиторию:</b>",
        reply_markup=get_chain_audience_keyboard(chain_id),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@router.callback_query(ChainAudienceCallback.filter())
async def chain_select_audience(callback: CallbackQuery, callback_data: ChainAudienceCallback, state: FSMContext):
    """Выбор аудитории для запуска цепочки"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    audience = callback_data.audience
    data = await state.get_data()
    chain_id = data.get('send_chain_id')

    if not chain_id:
        await callback.answer("❌ Ошибка: цепочка не выбрана", show_alert=True)
        return

    await state.update_data(send_audience=audience)

    # Получаем количество пользователей
    if audience == 'all':
        users = await db.get_broadcast_audience_users('all')
    elif audience == 'start_only':
        users = await db.get_broadcast_audience_users('start_only')
    elif audience == 'paid':
        users = await db.get_users_by_status('paid')
    elif audience == 'not_paid':
        users = await db.get_users_by_status('only_start')
        users2 = await db.get_users_by_status('clicked_no_screenshot')
        # Объединяем уникальные user_id
        user_ids = set(u['user_id'] for u in users)
        for u in users2:
            if u['user_id'] not in user_ids:
                users.append(u)
    else:
        users = []

    user_count = len(users)
    await state.update_data(send_user_count=user_count)

    chain = await db.get_chain(chain_id)

    audience_names = {
        'all': '👥 Все пользователи',
        'start_only': '👆 Только /start',
        'paid': '💰 Оплатившие',
        'not_paid': '❌ Не оплатившие'
    }

    await callback.message.edit_text(
        f"🚀 <b>ПОДТВЕРЖДЕНИЕ ЗАПУСКА</b>\n\n"
        f"📌 Цепочка: {chain['name']}\n"
        f"🎯 Аудитория: {audience_names.get(audience, audience)}\n"
        f"👥 Получателей: {user_count} чел.\n\n"
        "⚠️ <b>Цепочка будет запущена для всех выбранных пользователей!</b>\n"
        "Первое сообщение отправится сразу.",
        reply_markup=get_chain_confirm_send_keyboard(chain_id),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@router.callback_query(ChainEditCallback.filter(F.action == "confirm_send"))
async def chain_confirm_send(callback: CallbackQuery, callback_data: ChainEditCallback, state: FSMContext, bot: Bot):
    """Подтверждение и запуск цепочки"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    data = await state.get_data()
    chain_id = data.get('send_chain_id')
    audience = data.get('send_audience')

    if not chain_id or not audience:
        await callback.answer("❌ Ошибка данных", show_alert=True)
        return

    chain = await db.get_chain(chain_id)
    first_step = await db.get_first_chain_step(chain_id)

    if not chain or not first_step:
        await callback.answer("❌ Цепочка или шаги не найдены", show_alert=True)
        return

    # Получаем пользователей
    if audience == 'all':
        users = await db.get_broadcast_audience_users('all')
    elif audience == 'start_only':
        users = await db.get_broadcast_audience_users('start_only')
    elif audience == 'paid':
        users = await db.get_users_by_status('paid')
    elif audience == 'not_paid':
        users = await db.get_users_by_status('only_start')
        users2 = await db.get_users_by_status('clicked_no_screenshot')
        user_ids = set(u['user_id'] for u in users)
        for u in users2:
            if u['user_id'] not in user_ids:
                users.append(u)
    else:
        users = []

    await state.clear()

    # Запускаем цепочку для пользователей
    from keyboards.admin_kb import build_chain_step_keyboard

    success_count = 0
    fail_count = 0

    await callback.message.edit_text(
        f"⏳ <b>Запуск цепочки...</b>\n\n"
        f"Отправка первого шага {len(users)} пользователям...",
        parse_mode=ParseMode.HTML
    )

    buttons = await db.get_step_buttons(first_step['id'])

    for user in users:
        user_id = user['user_id']
        try:
            # Создаём состояние пользователя в цепочке
            await db.start_chain_for_user(user_id, chain_id, first_step['id'])

            # Отправляем первое сообщение
            reply_markup = build_chain_step_keyboard(
                buttons, chain_id, first_step['id']) if buttons else None

            if first_step.get('media_type') == 'photo' and first_step.get('media_file_id'):
                await bot.send_photo(
                    chat_id=user_id,
                    photo=first_step['media_file_id'],
                    caption=first_step['content'],
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.HTML
                )
            elif first_step.get('media_type') == 'video' and first_step.get('media_file_id'):
                await bot.send_video(
                    chat_id=user_id,
                    video=first_step['media_file_id'],
                    caption=first_step['content'],
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.HTML
                )
            else:
                await bot.send_message(
                    chat_id=user_id,
                    text=first_step['content'],
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.HTML
                )

            # Логируем отправку
            await db.log_chain_message(user_id, chain_id, first_step['id'])
            success_count += 1
        except Exception as e:
            logger.warning(f"Failed to send chain message to {user_id}: {e}")
            fail_count += 1

    await callback.message.edit_text(
        f"✅ <b>Цепочка запущена!</b>\n\n"
        f"📌 Цепочка: {chain['name']}\n"
        f"✅ Отправлено: {success_count}\n"
        f"❌ Ошибок: {fail_count}",
        reply_markup=get_chain_menu_keyboard(),
        parse_mode=ParseMode.HTML
    )

    logger.info(
        f"Chain {chain_id} started for {success_count} users by {callback.from_user.username}")
    await callback.answer("✅ Цепочка запущена!")


# ==================== User Management ====================

@router.message(F.text == "👥 Управление пользователями")
async def user_management_menu(message: Message, state: FSMContext):
    """Меню управления пользователями"""
    if not is_admin(message.from_user.username):
        return

    await state.clear()

    # Получаем общую статистику
    all_users = await db.get_all_users()
    paid_main = len([u for u in all_users if u.get('has_paid')])
    paid_fmd = len([u for u in all_users if u.get('has_paid_fmd')])
    paid_bundle = len([u for u in all_users if u.get('has_paid_bundle')])
    paid_dry = len([u for u in all_users if u.get('has_paid_dry')])

    await message.answer(
        "👥 <b>Управление пользователями</b>\n\n"
        f"📊 <b>Статистика:</b>\n"
        f"├ Всего пользователей: <b>{len(all_users)}</b>\n"
        f"├ 💰 Оплатили рационы: <b>{paid_main}</b>\n"
        f"├ 🥗 Оплатили FMD: <b>{paid_fmd}</b>\n"
        f"├ 🎁 Оплатили комплект: <b>{paid_bundle}</b>\n"
        f"└ 🔥 Оплатили Сушку: <b>{paid_dry}</b>\n\n"
        "Выберите действие:",
        reply_markup=get_user_management_menu(),
        parse_mode=ParseMode.HTML
    )


@router.callback_query(UserManageMenuCallback.filter(F.action == "list_all"))
async def user_list_all(callback: CallbackQuery, state: FSMContext):
    """Показать всех пользователей"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    await state.clear()
    users = await db.get_all_users()

    if not users:
        await callback.answer("📭 Нет пользователей", show_alert=True)
        return

    await state.update_data(user_list_filter="all")

    await callback.message.edit_text(
        f"👥 <b>Все пользователи</b>\n\n"
        f"Всего: {len(users)}\n\n"
        "💰 = Рационы | 🥗 = FMD | 🎁 = Комплект | ⚪ = Не оплачено",
        reply_markup=get_user_list_keyboard(users, page=0, filter_type="all"),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@router.callback_query(UserManageMenuCallback.filter(F.action == "back"))
async def user_back_to_menu(callback: CallbackQuery, state: FSMContext):
    """Вернуться в меню управления пользователями"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    await state.clear()

    all_users = await db.get_all_users()
    paid_main = len([u for u in all_users if u.get('has_paid')])
    paid_fmd = len([u for u in all_users if u.get('has_paid_fmd')])
    paid_bundle = len([u for u in all_users if u.get('has_paid_bundle')])
    paid_dry = len([u for u in all_users if u.get('has_paid_dry')])

    await callback.message.edit_text(
        "👥 <b>Управление пользователями</b>\n\n"
        f"📊 <b>Статистика:</b>\n"
        f"├ Всего пользователей: <b>{len(all_users)}</b>\n"
        f"├ 💰 Оплатили рационы: <b>{paid_main}</b>\n"
        f"├ 🥗 Оплатили FMD: <b>{paid_fmd}</b>\n"
        f"├ 🎁 Оплатили комплект: <b>{paid_bundle}</b>\n"
        f"└ 🔥 Оплатили Сушку: <b>{paid_dry}</b>\n\n"
        "Выберите действие:",
        reply_markup=get_user_management_menu(),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@router.callback_query(UserManageMenuCallback.filter(F.action == "search"))
async def user_search_start(callback: CallbackQuery, state: FSMContext):
    """Начать поиск пользователя"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    await state.set_state(UserSearchState.waiting_for_query)

    await callback.message.edit_text(
        "🔍 <b>Поиск пользователя</b>\n\n"
        "Отправьте:\n"
        "• <code>@username</code> — для поиска по нику\n"
        "• <code>user_id</code> — для поиска по ID\n"
        "• <code>имя</code> — для поиска по имени",
        parse_mode=ParseMode.HTML
    )

    await callback.message.answer(
        "❌ Для отмены нажмите кнопку ниже",
        reply_markup=get_cancel_keyboard()
    )
    await callback.answer()


@router.message(F.text == "❌ Отмена", UserSearchState.waiting_for_query)
async def user_search_cancel(message: Message, state: FSMContext):
    """Отмена поиска пользователя"""
    if not is_admin(message.from_user.username):
        return

    await state.clear()
    await message.answer(
        "❌ Поиск отменён.",
        reply_markup=get_admin_main_menu()
    )

    all_users = await db.get_all_users()
    paid_main = len([u for u in all_users if u.get('has_paid')])
    paid_fmd = len([u for u in all_users if u.get('has_paid_fmd')])
    paid_bundle = len([u for u in all_users if u.get('has_paid_bundle')])
    paid_dry = len([u for u in all_users if u.get('has_paid_dry')])

    await message.answer(
        "👥 <b>Управление пользователями</b>\n\n"
        f"📊 <b>Статистика:</b>\n"
        f"├ Всего пользователей: <b>{len(all_users)}</b>\n"
        f"├ 💰 Оплатили рационы: <b>{paid_main}</b>\n"
        f"├ 🥗 Оплатили FMD: <b>{paid_fmd}</b>\n"
        f"├ 🎁 Оплатили комплект: <b>{paid_bundle}</b>\n"
        f"└ 🔥 Оплатили Сушку: <b>{paid_dry}</b>\n\n"
        "Выберите действие:",
        reply_markup=get_user_management_menu(),
        parse_mode=ParseMode.HTML
    )


@router.message(UserSearchState.waiting_for_query)
async def user_search_process(message: Message, state: FSMContext):
    """Обработка поиска пользователя"""
    if not is_admin(message.from_user.username):
        return

    query = message.text.strip()
    users = await db.search_user_by_username_or_id(query)

    await state.clear()

    if not users:
        await message.answer(
            f"🔍 По запросу «<code>{query}</code>» ничего не найдено.",
            reply_markup=get_admin_main_menu(),
            parse_mode=ParseMode.HTML
        )
        await message.answer(
            "👥 <b>Управление пользователями</b>",
            reply_markup=get_user_management_menu(),
            parse_mode=ParseMode.HTML
        )
        return

    if len(users) == 1:
        # Если найден один пользователь — сразу показываем его карточку
        user = users[0]
        await show_user_card(message, user)
    else:
        # Показываем список найденных
        await message.answer(
            f"🔍 <b>Результаты поиска:</b> «{query}»\n\n"
            f"Найдено: {len(users)}\n\n"
            "💰 = Рационы | 🥗 = FMD | 🎁 = Комплект | ⚪ = Не оплачено",
            reply_markup=get_user_list_keyboard(
                users, page=0, filter_type="search"),
            parse_mode=ParseMode.HTML
        )


async def show_user_card(message_or_callback, user: dict):
    """Показать карточку пользователя"""
    user_id = user.get('user_id')
    username = user.get('username')
    first_name = user.get('first_name', 'Без имени')
    has_paid = user.get('has_paid', 0)
    has_paid_fmd = user.get('has_paid_fmd', 0)
    has_paid_bundle = user.get('has_paid_bundle', 0)
    has_paid_dry = user.get('has_paid_dry', 0)
    created_at = user.get('created_at', '')

    # Формируем ссылку на пользователя
    if username:
        user_link = f"@{username}"
    else:
        user_link = f'<a href="tg://user?id={user_id}">{first_name}</a>'

    # Статус оплат
    status_lines = []
    if has_paid:
        status_lines.append("💰 Рационы питания: ✅ Оплачено")
    else:
        status_lines.append("💰 Рационы питания: ❌ Не оплачено")

    if has_paid_fmd:
        status_lines.append("🥗 FMD Протокол: ✅ Оплачено")
    else:
        status_lines.append("🥗 FMD Протокол: ❌ Не оплачено")

    if has_paid_bundle:
        status_lines.append("🎁 Комплект: ✅ Оплачено")
    else:
        status_lines.append("🎁 Комплект: ❌ Не оплачено")

    if has_paid_dry:
        status_lines.append("🔥 Сушка: ✅ Оплачено")
    else:
        status_lines.append("🔥 Сушка: ❌ Не оплачено")

    status_text = "\n".join(status_lines)

    text = (
        f"👤 <b>Пользователь</b>\n\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"👤 Имя: {first_name}\n"
        f"📝 Username: {user_link}\n"
        f"📅 Регистрация: {created_at[:10] if created_at else 'н/д'}\n\n"
        f"<b>Статус оплат:</b>\n{status_text}"
    )

    keyboard = get_user_view_keyboard(user_id, bool(
        has_paid), bool(has_paid_fmd), bool(has_paid_bundle), bool(has_paid_dry))

    if hasattr(message_or_callback, 'edit_text'):
        # Это CallbackQuery.message
        await message_or_callback.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
    else:
        # Это Message
        await message_or_callback.answer(
            text,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )


@router.callback_query(UserListCallback.filter(F.action == "view"))
async def user_list_view(callback: CallbackQuery, callback_data: UserListCallback, state: FSMContext):
    """Показать список пользователей по фильтру"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    filter_type = callback_data.payment_filter
    users = await db.get_users_by_payment_filter(filter_type)

    if not users:
        await callback.answer("📭 Нет пользователей", show_alert=True)
        return

    filter_names = {
        'all': '👥 Все пользователи',
        'paid_main': '💰 Оплатившие рационы',
        'paid_fmd': '🥗 Оплатившие FMD',
        'paid_bundle': '🎁 Оплатившие комплект',
        'paid_dry': '🔥 Оплатившие Сушку'
    }

    await callback.message.edit_text(
        f"<b>{filter_names.get(filter_type, 'Пользователи')}</b>\n\n"
        f"Всего: {len(users)}\n\n"
        "💰 = Рационы | 🥗 = FMD | 🎁 = Комплект | 🔥 = Сушка | ⚪ = Не оплачено",
        reply_markup=get_user_list_keyboard(
            users, page=0, filter_type=filter_type),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@router.callback_query(UserListCallback.filter(F.action == "page"))
async def user_list_page(callback: CallbackQuery, callback_data: UserListCallback, state: FSMContext):
    """Пагинация списка пользователей"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    page = callback_data.page
    filter_type = callback_data.payment_filter
    users = await db.get_users_by_payment_filter(filter_type)

    filter_names = {
        'all': '👥 Все пользователи',
        'paid_main': '💰 Оплатившие рационы',
        'paid_fmd': '🥗 Оплатившие FMD',
        'paid_bundle': '🎁 Оплатившие комплект',
        'paid_dry': '🔥 Оплатившие Сушку',
        'search': '🔍 Результаты поиска'
    }

    await callback.message.edit_text(
        f"<b>{filter_names.get(filter_type, 'Пользователи')}</b>\n\n"
        f"Всего: {len(users)}\n\n"
        "💰 = Рационы | 🥗 = FMD | 🎁 = Комплект | 🔥 = Сушка | ⚪ = Не оплачено",
        reply_markup=get_user_list_keyboard(
            users, page=page, filter_type=filter_type),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@router.callback_query(UserActionCallback.filter(F.action == "view"))
async def user_view(callback: CallbackQuery, callback_data: UserActionCallback):
    """Просмотр карточки пользователя"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    user_id = callback_data.user_id
    user = await db.get_user(user_id)

    if not user:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return

    await show_user_card(callback.message, user)
    await callback.answer()


@router.callback_query(UserActionCallback.filter(F.action == "reset_main"))
async def user_reset_main_confirm(callback: CallbackQuery, callback_data: UserActionCallback):
    """Подтверждение сброса оплаты рациона"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    user_id = callback_data.user_id
    user = await db.get_user(user_id)

    if not user:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return

    username = user.get('username')
    first_name = user.get('first_name', 'Без имени')
    user_display = f"@{username}" if username else first_name

    await callback.message.edit_text(
        f"⚠️ <b>Подтверждение сброса</b>\n\n"
        f"Вы уверены, что хотите сбросить оплату <b>рационов питания</b> для пользователя {user_display}?\n\n"
        f"ID: <code>{user_id}</code>",
        reply_markup=get_user_confirm_reset_keyboard(user_id, "main"),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@router.callback_query(UserActionCallback.filter(F.action == "reset_fmd"))
async def user_reset_fmd_confirm(callback: CallbackQuery, callback_data: UserActionCallback):
    """Подтверждение сброса оплаты FMD"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    user_id = callback_data.user_id
    user = await db.get_user(user_id)

    if not user:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return

    username = user.get('username')
    first_name = user.get('first_name', 'Без имени')
    user_display = f"@{username}" if username else first_name

    await callback.message.edit_text(
        f"⚠️ <b>Подтверждение сброса</b>\n\n"
        f"Вы уверены, что хотите сбросить оплату <b>FMD Протокола</b> для пользователя {user_display}?\n\n"
        f"ID: <code>{user_id}</code>",
        reply_markup=get_user_confirm_reset_keyboard(user_id, "fmd"),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@router.callback_query(UserActionCallback.filter(F.action == "reset_bundle"))
async def user_reset_bundle_confirm(callback: CallbackQuery, callback_data: UserActionCallback):
    """Подтверждение сброса оплаты комплекта"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    user_id = callback_data.user_id
    user = await db.get_user(user_id)

    if not user:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return

    username = user.get('username')
    first_name = user.get('first_name', 'Без имени')
    user_display = f"@{username}" if username else first_name

    await callback.message.edit_text(
        f"⚠️ <b>Подтверждение сброса</b>\n\n"
        f"Вы уверены, что хотите сбросить оплату <b>комплекта</b> для пользователя {user_display}?\n\n"
        f"ID: <code>{user_id}</code>",
        reply_markup=get_user_confirm_reset_keyboard(user_id, "bundle"),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@router.callback_query(UserActionCallback.filter(F.action == "reset_all"))
async def user_reset_all_confirm(callback: CallbackQuery, callback_data: UserActionCallback):
    """Подтверждение сброса всех оплат"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    user_id = callback_data.user_id
    user = await db.get_user(user_id)

    if not user:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return

    username = user.get('username')
    first_name = user.get('first_name', 'Без имени')
    user_display = f"@{username}" if username else first_name

    await callback.message.edit_text(
        f"🚨 <b>ВНИМАНИЕ!</b>\n\n"
        f"Вы уверены, что хотите сбросить <b>ВСЕ ОПЛАТЫ</b> для пользователя {user_display}?\n\n"
        f"ID: <code>{user_id}</code>\n\n"
        "Это действие удалит доступ ко всем продуктам!",
        reply_markup=get_user_confirm_reset_keyboard(user_id, "all"),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@router.callback_query(UserActionCallback.filter(F.action == "confirm_main"))
async def user_confirm_reset_main(callback: CallbackQuery, callback_data: UserActionCallback):
    """Выполнить сброс оплаты рациона"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    user_id = callback_data.user_id
    success = await db.reset_user_payment(user_id, 'main')

    if success:
        logger.info(
            f"Payment reset (main) for user {user_id} by {callback.from_user.username}")
        await callback.answer("✅ Оплата рациона сброшена!", show_alert=True)

        # Обновляем карточку пользователя
        user = await db.get_user(user_id)
        if user:
            await show_user_card(callback.message, user)
    else:
        await callback.answer("❌ Ошибка сброса", show_alert=True)


@router.callback_query(UserActionCallback.filter(F.action == "confirm_fmd"))
async def user_confirm_reset_fmd(callback: CallbackQuery, callback_data: UserActionCallback):
    """Выполнить сброс оплаты FMD"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    user_id = callback_data.user_id
    success = await db.reset_user_payment(user_id, 'fmd')

    if success:
        logger.info(
            f"Payment reset (fmd) for user {user_id} by {callback.from_user.username}")
        await callback.answer("✅ Оплата FMD сброшена!", show_alert=True)

        user = await db.get_user(user_id)
        if user:
            await show_user_card(callback.message, user)
    else:
        await callback.answer("❌ Ошибка сброса", show_alert=True)


@router.callback_query(UserActionCallback.filter(F.action == "confirm_bundle"))
async def user_confirm_reset_bundle(callback: CallbackQuery, callback_data: UserActionCallback):
    """Выполнить сброс оплаты комплекта"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    user_id = callback_data.user_id
    success = await db.reset_user_payment(user_id, 'bundle')

    if success:
        logger.info(
            f"Payment reset (bundle) for user {user_id} by {callback.from_user.username}")
        await callback.answer("✅ Оплата комплекта сброшена!", show_alert=True)

        user = await db.get_user(user_id)
        if user:
            await show_user_card(callback.message, user)
    else:
        await callback.answer("❌ Ошибка сброса", show_alert=True)


@router.callback_query(UserActionCallback.filter(F.action == "reset_dry"))
async def user_reset_dry_confirm(callback: CallbackQuery, callback_data: UserActionCallback):
    """Подтверждение сброса оплаты Сушки"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    user_id = callback_data.user_id
    user = await db.get_user(user_id)

    if not user:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return

    username = user.get('username')
    first_name = user.get('first_name', 'Без имени')
    user_display = f"@{username}" if username else first_name

    await callback.message.edit_text(
        f"⚠️ <b>Подтверждение сброса</b>\n\n"
        f"Вы уверены, что хотите сбросить оплату <b>Сушки</b> для пользователя {user_display}?\n\n"
        f"ID: <code>{user_id}</code>",
        reply_markup=get_user_confirm_reset_keyboard(user_id, "dry"),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@router.callback_query(UserActionCallback.filter(F.action == "confirm_dry"))
async def user_confirm_reset_dry(callback: CallbackQuery, callback_data: UserActionCallback):
    """Выполнить сброс оплаты Сушки"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    user_id = callback_data.user_id
    success = await db.reset_user_payment(user_id, 'dry')

    if success:
        logger.info(
            f"Payment reset (dry) for user {user_id} by {callback.from_user.username}")
        await callback.answer("✅ Оплата Сушки сброшена!", show_alert=True)

        user = await db.get_user(user_id)
        if user:
            await show_user_card(callback.message, user)
    else:
        await callback.answer("❌ Ошибка сброса", show_alert=True)


@router.callback_query(UserActionCallback.filter(F.action == "confirm_all"))
async def user_confirm_reset_all(callback: CallbackQuery, callback_data: UserActionCallback):
    """Выполнить сброс всех оплат"""
    if not is_admin(callback.from_user.username):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    user_id = callback_data.user_id
    success = await db.reset_user_payment(user_id, 'all')

    if success:
        logger.info(
            f"Payment reset (ALL) for user {user_id} by {callback.from_user.username}")
        await callback.answer("✅ Все оплаты сброшены!", show_alert=True)

        user = await db.get_user(user_id)
        if user:
            await show_user_card(callback.message, user)
    else:
        await callback.answer("❌ Ошибка сброса", show_alert=True)


# ==================== Отдел Заботы (Поддержка) ====================

@router.callback_query(SupportReplyCallback.filter(F.action == "reply"))
async def support_reply_start(callback: CallbackQuery, callback_data: SupportReplyCallback, state: FSMContext):
    """Модератор нажал кнопку 'Ответить' на вопрос пользователя"""
    user_id = callback_data.user_id
    question_id = callback_data.question_id

    # Извлекаем текст вопроса из оригинального сообщения
    original_text = callback.message.text or ""
    question_text = ""

    # Парсим текст вопроса из сообщения (ищем после "❓ Вопрос:")
    if "❓" in original_text:
        parts = original_text.split("❓")
        if len(parts) > 1:
            # Берём всё после "❓ Вопрос:"
            question_part = parts[1]
            # Убираем префикс "Вопрос:" если есть
            if "Вопрос:" in question_part:
                question_text = question_part.split("Вопрос:", 1)[1].strip()
            else:
                question_text = question_part.strip()

    # Сохраняем данные для ответа
    await state.update_data(
        support_user_id=user_id,
        support_question_id=question_id,
        support_original_message_id=callback.message.message_id,
        support_question_text=question_text
    )
    await state.set_state(SupportReplyState.waiting_for_reply)

    # Формируем сообщение с текстом вопроса
    reply_prompt = (
        f"💬 <b>Ответ пользователю</b>\n\n"
        f"🆔 ID: <code>{user_id}</code>\n"
    )

    if question_text:
        reply_prompt += f"\n❓ <b>Вопрос:</b>\n<i>{question_text}</i>\n"

    reply_prompt += (
        f"\nНапиши ответ и он будет отправлен пользователю.\n"
        f"Отправь /cancel для отмены."
    )

    await callback.message.answer(
        reply_prompt,
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@router.message(Command("cancel"), SupportReplyState.waiting_for_reply)
async def cancel_support_reply(message: Message, state: FSMContext):
    """Отмена ответа модератора"""
    await state.clear()
    await message.answer(
        "❌ <b>Ответ отменён</b>",
        parse_mode=ParseMode.HTML
    )


@router.message(SupportReplyState.waiting_for_reply, F.text)
async def send_support_reply(message: Message, state: FSMContext, bot: Bot):
    """Отправка ответа модератора пользователю"""
    data = await state.get_data()
    user_id = data.get('support_user_id')
    original_message_id = data.get('support_original_message_id')
    reply_text = message.text

    if not user_id:
        await message.answer("❌ Ошибка: не найден пользователь")
        await state.clear()
        return

    try:
        # Отправляем ответ пользователю
        await bot.send_message(
            chat_id=user_id,
            text=(
                "💚 <b>Ответ от Отдела Заботы:</b>\n\n"
                f"{reply_text}"
            ),
            parse_mode=ParseMode.HTML
        )

        # Обновляем сообщение в канале модераторов (убираем кнопку)
        if original_message_id:
            try:
                await bot.edit_message_reply_markup(
                    chat_id=ADMIN_CHANNEL_ID,
                    message_id=original_message_id,
                    reply_markup=None
                )
            except Exception:
                pass  # Игнорируем если не получилось

        await state.clear()

        await message.answer(
            f"✅ <b>Ответ отправлен!</b>\n\n"
            f"Пользователь {user_id} получил твой ответ.",
            parse_mode=ParseMode.HTML
        )

        logger.info(
            f"Support reply sent to user {user_id} by {message.from_user.username}")

    except Exception as e:
        logger.error(f"Failed to send support reply to user {user_id}: {e}")
        await message.answer(
            f"❌ <b>Ошибка отправки</b>\n\n"
            f"Не удалось отправить ответ пользователю.\n"
            f"Возможно, пользователь заблокировал бота.",
            parse_mode=ParseMode.HTML
        )
        await state.clear()


@router.message(SupportReplyState.waiting_for_reply)
async def wrong_support_reply_content(message: Message):
    """Неверный формат ответа - ожидаем текст"""
    await message.answer(
        "⚠️ <b>Пожалуйста, отправь ответ текстом.</b>\n\n"
        "Если хочешь отменить — отправь /cancel",
        parse_mode=ParseMode.HTML
    )


# Обработчик ответов реплаем на вопросы в канале модераторов
@router.message(F.chat.id == ADMIN_CHANNEL_ID, F.reply_to_message)
async def support_reply_via_thread(message: Message, bot: Bot):
    """
    Автоматическая пересылка ответа модератора пользователю,
    когда модератор отвечает реплаем на сообщение с вопросом в канале.
    """
    original_message = message.reply_to_message
    original_text = original_message.text or ""

    # Проверяем что это ответ на сообщение с вопросом от поддержки
    if "Новый вопрос в Отдел Заботы" not in original_text and "🆔 ID:" not in original_text:
        return  # Это не вопрос от поддержки, игнорируем

    # Извлекаем user_id из оригинального сообщения
    # Ищем паттерн "🆔 ID: 1234567890"
    match = re.search(r'🆔 ID:\s*(\d+)', original_text)
    if not match:
        return  # Не нашли ID пользователя

    user_id = int(match.group(1))
    reply_text = message.text

    if not reply_text:
        return  # Только текстовые ответы

    try:
        # Отправляем ответ пользователю
        await bot.send_message(
            chat_id=user_id,
            text=(
                "💚 <b>Ответ от Отдела Заботы:</b>\n\n"
                f"{reply_text}"
            ),
            parse_mode=ParseMode.HTML
        )

        # Убираем кнопку "Ответить" с оригинального сообщения
        try:
            await bot.edit_message_reply_markup(
                chat_id=ADMIN_CHANNEL_ID,
                message_id=original_message.message_id,
                reply_markup=None
            )
        except Exception:
            pass

        # Подтверждаем модератору что ответ отправлен
        await message.reply(
            f"✅ Ответ отправлен пользователю {user_id}",
            parse_mode=ParseMode.HTML
        )

        logger.info(
            f"Support reply via thread sent to user {user_id} by {message.from_user.username}")

    except Exception as e:
        logger.error(
            f"Failed to send support reply via thread to user {user_id}: {e}")
        await message.reply(
            "❌ Не удалось отправить ответ. Возможно, пользователь заблокировал бота.",
            parse_mode=ParseMode.HTML
        )
