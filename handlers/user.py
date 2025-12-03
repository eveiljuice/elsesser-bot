import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandStart
from aiogram.enums import ParseMode

import database as db
from config import PAYMENT_AMOUNT, PAYMENT_DETAILS, ADMIN_CHANNEL_ID
from keyboards.user_kb import (
    get_main_menu,
    get_payment_keyboard,
    get_calories_keyboard,
    get_days_keyboard,
    get_back_to_calories_keyboard,
)
from keyboards.calculator_kb import get_start_calculator_keyboard
from keyboards.admin_kb import get_payment_verification_keyboard
from keyboards.callbacks import PaymentCallback, CaloriesCallback, DayCallback, BackCallback
from data.recipes import get_recipe_text_async, get_available_calories

logger = logging.getLogger(__name__)
router = Router(name="user")


# ==================== Команды ====================

@router.message(CommandStart())
async def cmd_start(message: Message):
    """Обработка команды /start"""
    user = message.from_user
    await db.add_user(user.id, user.username, user.first_name)

    has_paid = await db.check_payment_status(user.id)

    if has_paid:
        await message.answer(
            f"👋 <b>Привет, {user.first_name}!</b>\n\n"
            "🎉 У тебя есть доступ к рационам питания!\n"
            "Выбери нужное действие в меню ниже:",
            reply_markup=get_main_menu(),
            parse_mode=ParseMode.HTML
        )

        # Проверяем, проходил ли калькулятор
        has_calc = await db.has_calculator_result(user.id)
        if not has_calc:
            await message.answer(
                "💡 <b>Рекомендуем пройти калькулятор калорий!</b>\n\n"
                "Это поможет подобрать рацион, который идеально подходит именно вам.\n"
                "Нажмите кнопку ниже 👇",
                reply_markup=get_start_calculator_keyboard(),
                parse_mode=ParseMode.HTML
            )
    else:
        await message.answer(
            f"👋 <b>Привет, {user.first_name}!</b>\n\n"
            "🍽 Я бот с рационами питания на разную калорийность "
            "(от 1600 до 2100 ккал).\n\n"
            "📋 Каждый рацион включает:\n"
            "• Завтрак, обед и ужин\n"
            "• Подробные рецепты\n"
            "• Точное КБЖУ\n\n"
            f"💰 <b>Стоимость доступа: {PAYMENT_AMOUNT} ₽</b>\n\n"
            "Для получения доступа оплати по реквизитам ниже 👇",
            parse_mode=ParseMode.HTML
        )
        await show_payment_info(message)


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Обработка команды /help"""
    await message.answer(
        "❓ <b>Помощь</b>\n\n"
        "🤖 <b>Что умеет этот бот:</b>\n"
        "• Предоставляет рационы питания на разную калорийность\n"
        "• Подробные рецепты с КБЖУ\n"
        "• Простая навигация по дням\n\n"
        "📝 <b>Команды:</b>\n"
        "/start — Начать работу с ботом\n"
        "/help — Показать эту справку\n"
        "/status — Проверить статус оплаты\n\n"
        "💬 <b>По вопросам обращайтесь к администратору в лс @popdevp.</b>",
        parse_mode=ParseMode.HTML
    )


@router.message(Command("status"))
async def cmd_status(message: Message):
    """Проверка статуса оплаты"""
    user_id = message.from_user.id
    has_paid = await db.check_payment_status(user_id)
    has_pending = await db.has_pending_request(user_id)

    if has_paid:
        await message.answer(
            "✅ <b>Статус: Оплачено</b>\n\n"
            "У тебя есть полный доступ ко всем рационам! 🎉",
            reply_markup=get_main_menu(),
            parse_mode=ParseMode.HTML
        )
    elif has_pending:
        await message.answer(
            "⏳ <b>Статус: Ожидает проверки</b>\n\n"
            "Твой запрос на проверку оплаты отправлен.\n"
            "Пожалуйста, подожди — мы скоро проверим! 🔍",
            parse_mode=ParseMode.HTML
        )
    else:
        await message.answer(
            "❌ <b>Статус: Не оплачено</b>\n\n"
            f"Для получения доступа оплати {PAYMENT_AMOUNT} ₽\n"
            "и нажми кнопку «Я оплатил(а)».",
            parse_mode=ParseMode.HTML
        )
        await show_payment_info(message)


# ==================== Кнопки главного меню ====================

@router.message(F.text == "🍽 Выбрать рацион")
async def choose_ration(message: Message):
    """Выбор рациона"""
    has_paid = await db.check_payment_status(message.from_user.id)

    if not has_paid:
        await message.answer(
            "⛔ <b>Доступ ограничен</b>\n\n"
            f"Для просмотра рационов необходимо оплатить доступ ({PAYMENT_AMOUNT} ₽).",
            parse_mode=ParseMode.HTML
        )
        await show_payment_info(message)
        return

    await message.answer(
        "🔥 <b>Выбери калорийность рациона:</b>\n\n"
        "Доступные варианты от 1600 до 2100 ккал.",
        reply_markup=get_calories_keyboard(),
        parse_mode=ParseMode.HTML
    )


@router.message(F.text == "📋 Мой статус")
async def my_status(message: Message):
    """Проверка статуса через кнопку меню"""
    await cmd_status(message)


@router.message(F.text == "❓ Помощь")
async def help_button(message: Message):
    """Помощь через кнопку меню"""
    await cmd_help(message)


@router.message(F.text == "📊 Рассчитать калории")
async def calculate_calories_button(message: Message):
    """Запуск калькулятора калорий"""
    has_paid = await db.check_payment_status(message.from_user.id)

    if not has_paid:
        await message.answer(
            "⛔ <b>Доступ ограничен</b>\n\n"
            f"Для использования калькулятора необходимо оплатить доступ ({PAYMENT_AMOUNT} ₽).",
            parse_mode=ParseMode.HTML
        )
        await show_payment_info(message)
        return

    # Проверяем, проходил ли пользователь калькулятор ранее
    last_result = await db.get_last_calculator_result(message.from_user.id)

    if last_result:
        await message.answer(
            "📊 <b>Калькулятор калорий</b>\n\n"
            f"В прошлый раз ваши результаты были:\n"
            f"• Калорийность: <b>{last_result['calories']}</b> ккал\n"
            f"• Белки: <b>{last_result['protein']}</b> г\n"
            f"• Жиры: <b>{last_result['fats']}</b> г\n"
            f"• Углеводы: <b>{last_result['carbs']}</b> г\n\n"
            "Хотите пересчитать?",
            reply_markup=get_start_calculator_keyboard(),
            parse_mode=ParseMode.HTML
        )
    else:
        await message.answer(
            "📊 <b>Калькулятор калорий</b>\n\n"
            "Чтобы подобрать рацион, который подходит именно вам, "
            "пройдите короткую анкету. Калькулятор рассчитает:\n\n"
            "• 🔥 Вашу дневную калорийность\n"
            "• 🥩 Норму белков, жиров и углеводов\n"
            "• ⚖️ Оптимальный вес\n"
            "• 📏 Индекс массы тела\n\n"
            "Это займёт всего 2 минуты 👇",
            reply_markup=get_start_calculator_keyboard(),
            parse_mode=ParseMode.HTML
        )


# ==================== Оплата ====================

async def show_payment_info(message: Message):
    """Показать информацию для оплаты"""
    # Заменяем \n в строке на реальные переносы
    payment_details = PAYMENT_DETAILS.replace('\\n', '\n')

    await message.answer(
        f"💳 <b>Реквизиты для оплаты:</b>\n\n"
        f"<code>{payment_details}</code>\n\n"
        f"💰 <b>Сумма: {PAYMENT_AMOUNT} ₽</b>\n\n"
        "⚠️ <b>ВАЖНО:</b>\n"
        "• Внимательно проверьте реквизиты\n"
        "• После оплаты нажмите кнопку ниже\n"
        "• Проверка занимает до 24 часов",
        reply_markup=get_payment_keyboard(),
        parse_mode=ParseMode.HTML
    )


@router.callback_query(PaymentCallback.filter())
async def payment_done(callback: CallbackQuery, bot: Bot):
    """Пользователь нажал 'Я оплатил(а)'"""
    user = callback.from_user

    # Проверяем, нет ли уже активного запроса
    has_pending = await db.has_pending_request(user.id)
    if has_pending:
        await callback.answer(
            "⏳ У тебя уже есть запрос на проверке!",
            show_alert=True
        )
        return

    # Проверяем, не оплачено ли уже
    has_paid = await db.check_payment_status(user.id)
    if has_paid:
        await callback.answer(
            "✅ У тебя уже есть доступ!",
            show_alert=True
        )
        return

    # Отправляем сообщение админам
    # Формируем отображение пользователя:
    # - Если есть username: @username
    # - Если нет username: кликабельная ссылка с именем через tg://user
    if user.username:
        username_display = f"@{user.username}"
    else:
        # HTML mention - кликабельная ссылка на пользователя
        full_name = f"{user.first_name or ''} {user.last_name or ''}".strip(
        ) or f"User {user.id}"
        username_display = f'<a href="tg://user?id={user.id}">{full_name}</a>'

    admin_message = await bot.send_message(
        chat_id=ADMIN_CHANNEL_ID,
        text=(
            "🔔 <b>Новый запрос на проверку оплаты!</b>\n\n"
            f"👤 Пользователь: {username_display}\n"
            f"📝 Имя: {user.first_name or 'Не указано'}\n"
            f"🆔 ID: <code>{user.id}</code>\n\n"
            "Проверьте оплату и выберите действие:"
        ),
        parse_mode=ParseMode.HTML
    )

    # Создаём запрос в БД
    request_id = await db.create_payment_request(user.id, admin_message.message_id)

    # Добавляем кнопки к сообщению админа
    await admin_message.edit_reply_markup(
        reply_markup=get_payment_verification_keyboard(user.id, request_id)
    )

    await callback.answer("✅ Запрос отправлен на проверку!")
    await callback.message.answer(
        "✅ <b>Запрос отправлен!</b>\n\n"
        "Администратор проверит оплату в ближайшее время.\n"
        "Ты получишь уведомление о результате.\n\n"
        "⏳ Обычно проверка занимает до 24 часов.",
        parse_mode=ParseMode.HTML
    )


# ==================== Выбор калорийности и дней ====================

@router.callback_query(CaloriesCallback.filter())
async def select_calories(callback: CallbackQuery, callback_data: CaloriesCallback):
    """Выбор калорийности"""
    # Проверяем доступ
    has_paid = await db.check_payment_status(callback.from_user.id)
    if not has_paid:
        await callback.answer("⛔ Сначала оплати доступ!", show_alert=True)
        return

    calories = callback_data.calories

    await callback.message.edit_text(
        f"📅 <b>Рацион на {calories} ккал</b>\n\n"
        "Выбери день:",
        reply_markup=get_days_keyboard(calories),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@router.callback_query(DayCallback.filter())
async def select_day(callback: CallbackQuery, callback_data: DayCallback):
    """Выбор дня и показ рецептов"""
    # Проверяем доступ
    has_paid = await db.check_payment_status(callback.from_user.id)
    if not has_paid:
        await callback.answer("⛔ Сначала оплати доступ!", show_alert=True)
        return

    calories = callback_data.calories
    day = callback_data.day

    # Используем асинхронную версию для поддержки кастомных рецептов из БД
    recipe_text = await get_recipe_text_async(calories, day)

    # Отправляем новое сообщение с рецептами (они длинные)
    await callback.message.answer(
        recipe_text,
        reply_markup=get_back_to_calories_keyboard(),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@router.callback_query(BackCallback.filter())
async def go_back(callback: CallbackQuery, callback_data: BackCallback):
    """Кнопка 'Назад'"""
    if callback_data.to == "calories":
        await callback.message.edit_text(
            "🔥 <b>Выбери калорийность рациона:</b>\n\n"
            "Доступные варианты от 1600 до 2100 ккал.",
            reply_markup=get_calories_keyboard(),
            parse_mode=ParseMode.HTML
        )
    await callback.answer()
