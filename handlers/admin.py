import logging
import re
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
    AdminEditCallback
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
    get_cancel_keyboard
)
from data.recipes import RECIPES, get_recipe_from_db

logger = logging.getLogger(__name__)
router = Router(name="admin")


# ==================== FSM States ====================

class AdminEditState(StatesGroup):
    """Состояния для редактирования контента"""
    waiting_for_content = State()


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
        f"└ Всего дней рационов: {sum(len(days) for days in RECIPES.values())}",
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
            "🤖 <i>Отчёт сформирован вручную</i>"
        )

        await bot.send_message(
            chat_id=ADMIN_CHANNEL_ID,
            text=message_text,
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

    logger.info(
        f"Admin {callback.from_user.id} approving payment: user_id={user_id}, request_id={request_id}")

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

    logger.info(f"Processing payment approval for user {user_id}")

    # Обновляем статус оплаты пользователя
    await db.set_payment_status(user_id, True)
    await db.update_payment_request(request_id, 'approved')

    # Логируем событие и отменяем все pending follow-up сообщения
    await db.log_event(user_id, EventType.PAYMENT_APPROVED, f"approved_by:{callback.from_user.id}")
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

    # Уведомляем пользователя и предлагаем пройти калькулятор
    try:
        # Сначала отправляем меню
        await bot.send_message(
            chat_id=user_id,
            text=(
                "🎉 <b>Оплата подтверждена!</b>\n\n"
                "Теперь у тебя есть полный доступ ко всем рационам питания!"
            ),
            reply_markup=get_main_menu(),
            parse_mode=ParseMode.HTML
        )

        # Затем предлагаем пройти калькулятор
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
            f"Payment approved for user {user_id} by admin {callback.from_user.id}")
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
    await db.log_event(user_id, EventType.PAYMENT_REJECTED, f"rejected_by:{callback.from_user.id}")

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
        await bot.send_message(
            chat_id=user_id,
            text=(
                "❌ <b>Оплата не подтверждена</b>\n\n"
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
            f"Payment rejected for user {user_id} by admin {callback.from_user.id}")
    except Exception as e:
        logger.error(f"Failed to notify user {user_id}: {e}")
        await callback.answer(
            f"❌ Оплата отклонена, но не удалось уведомить пользователя",
            show_alert=True
        )
        return

    await callback.answer("❌ Оплата отклонена")
