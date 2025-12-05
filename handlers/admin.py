import logging
import re
from aiogram import Router, Bot, F
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import database as db
from config import ADMIN_USERNAMES
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
    """Показать статистику"""
    if not is_admin(message.from_user.username):
        return

    # Простая статистика
    custom_recipes = await db.get_all_custom_recipes()

    await message.answer(
        "📊 <b>Статистика</b>\n\n"
        f"📝 Кастомных рецептов: {len(custom_recipes)}\n"
        f"📋 Калорийностей в базе: {len(RECIPES)}\n"
        f"📅 Всего дней рационов: {sum(len(days) for days in RECIPES.values())}",
        parse_mode=ParseMode.HTML
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

    # Получаем информацию о запросе
    request = await db.get_payment_request(request_id)
    if not request:
        await callback.answer("❌ Запрос не найден!", show_alert=True)
        return

    if request['status'] != 'pending':
        await callback.answer("⚠️ Этот запрос уже обработан!", show_alert=True)
        return

    # Обновляем статус оплаты пользователя
    await db.set_payment_status(user_id, True)
    await db.update_payment_request(request_id, 'approved')

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
    await callback.message.edit_text(
        callback.message.text + f"\n\n✅ <b>ОДОБРЕНО</b>\n"
        f"👤 Обработал: {admin_display}",
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
    await callback.message.edit_text(
        callback.message.text + f"\n\n❌ <b>ОТКЛОНЕНО</b>\n"
        f"👤 Обработал: {admin_display}",
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
