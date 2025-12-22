import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.filters import Command, CommandStart
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import database as db
from database import EventType
from config import PAYMENT_AMOUNT, PAYMENT_DETAILS, ADMIN_CHANNEL_ID, FMD_PAYMENT_AMOUNT
from keyboards.user_kb import (
    get_main_menu,
    get_payment_keyboard,
    get_calories_keyboard,
    get_days_keyboard,
    get_back_to_calories_keyboard,
    get_fmd_payment_keyboard,
    get_fmd_days_keyboard,
    get_back_to_fmd_days_keyboard,
    get_products_keyboard,
)
from keyboards.calculator_kb import get_start_calculator_keyboard
from keyboards.admin_kb import get_payment_verification_keyboard
from keyboards.callbacks import (
    PaymentCallback, CaloriesCallback, DayCallback, BackCallback,
    FMDPaymentCallback, FMDDayCallback, ProductSelectCallback, BackToProductsCallback,
    FMDInfoCallback
)
from data.recipes import (
    get_recipe_text_async, get_available_calories, get_fmd_recipe_text_async,
    get_fmd_shopping_list, get_fmd_info
)

logger = logging.getLogger(__name__)
router = Router(name="user")


# ==================== FSM States ====================

class PaymentState(StatesGroup):
    """Состояния для процесса оплаты основного рациона"""
    waiting_for_screenshot = State()


class FMDPaymentState(StatesGroup):
    """Состояния для процесса оплаты FMD протокола"""
    waiting_for_screenshot = State()


# ==================== Команды ====================

@router.message(CommandStart())
async def cmd_start(message: Message):
    """Обработка команды /start"""
    user = message.from_user
    await db.add_user(user.id, user.username, user.first_name)
    
    # Логируем событие /start
    await db.log_event(user.id, EventType.START_COMMAND)

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
            "и нажми кнопку «Я оплатила».",
            parse_mode=ParseMode.HTML
        )
        await show_payment_info(message)


# ==================== Кнопки главного меню ====================

@router.message(F.text == "🍽 Выбрать рацион")
async def choose_ration(message: Message):
    """Выбор рациона - показываем меню продуктов"""
    user_id = message.from_user.id
    has_paid = await db.check_payment_status(user_id)
    has_paid_fmd = await db.check_fmd_payment_status(user_id)

    # Показываем меню продуктов с указанием что оплачено
    await message.answer(
        "🍽 <b>Выбери рацион питания:</b>\n\n"
        "📋 <b>Рационы питания (14 дней)</b>\n"
        "Сбалансированное меню на каждый день с калорийностью от 1200 до 2100 ккал.\n\n"
        "🥗 <b>FMD Протокол (5 дней)</b>\n"
        "Диета, имитирующая голодание — программа для оздоровления организма.",
        reply_markup=get_products_keyboard(has_main=has_paid, has_fmd=has_paid_fmd),
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


def get_cancel_payment_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура отмены отправки скриншота"""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True
    )


@router.callback_query(PaymentCallback.filter())
async def payment_done(callback: CallbackQuery, bot: Bot, state: FSMContext):
    """Пользователь нажал 'Я оплатил(а)' - просим скриншот"""
    user = callback.from_user
    
    # Логируем нажатие кнопки "Я оплатил(а)"
    await db.log_event(user.id, EventType.PAYMENT_BUTTON_CLICKED)

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

    # Устанавливаем состояние ожидания скриншота
    await state.set_state(PaymentState.waiting_for_screenshot)

    await callback.answer()
    await callback.message.answer(
        "📸 <b>Отправь скриншот оплаты</b>\n\n"
        "Пожалуйста, отправь фото/скриншот подтверждения перевода.\n"
        "Это поможет модераторам быстрее проверить твою оплату.\n\n"
        "⚠️ <i>На скриншоте должны быть видны: сумма, дата и получатель.</i>",
        reply_markup=get_cancel_payment_keyboard(),
        parse_mode=ParseMode.HTML
    )


@router.message(F.text == "❌ Отмена", PaymentState.waiting_for_screenshot)
async def cancel_payment_screenshot(message: Message, state: FSMContext):
    """Отмена отправки скриншота"""
    await state.clear()
    await message.answer(
        "❌ Отправка отменена.\n\n"
        "Когда будешь готов — нажми кнопку «Я оплатил(а)» снова.",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode=ParseMode.HTML
    )


@router.message(F.photo, PaymentState.waiting_for_screenshot)
async def receive_payment_screenshot(message: Message, bot: Bot, state: FSMContext):
    """Получение скриншота оплаты и отправка модераторам"""
    user = message.from_user
    
    # Логируем отправку скриншота
    await db.log_event(user.id, EventType.SCREENSHOT_SENT)

    # Очищаем состояние
    await state.clear()

    # Получаем file_id самого большого фото (лучшее качество)
    photo = message.photo[-1]
    photo_file_id = photo.file_id

    # Формируем отображение пользователя
    if user.username:
        username_display = f"@{user.username}"
    else:
        full_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or f"User {user.id}"
        username_display = f'<a href="tg://user?id={user.id}">{full_name}</a>'

    # Отправляем фото со скриншотом в канал модераторов
    admin_message = await bot.send_photo(
        chat_id=ADMIN_CHANNEL_ID,
        photo=photo_file_id,
        caption=(
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

    await message.answer(
        "✅ <b>Запрос отправлен!</b>\n\n"
        "Скриншот оплаты передан модераторам.\n"
        "Ты получишь уведомление о результате.\n\n"
        "⏳ Обычно проверка занимает до 24 часов.",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode=ParseMode.HTML
    )


@router.message(PaymentState.waiting_for_screenshot)
async def wrong_payment_content(message: Message):
    """Неверный формат - ожидаем фото"""
    await message.answer(
        "⚠️ <b>Пожалуйста, отправь фото/скриншот оплаты.</b>\n\n"
        "Если хочешь отменить — нажми кнопку «❌ Отмена».",
        parse_mode=ParseMode.HTML
    )


# ==================== Выбор продукта ====================

@router.callback_query(ProductSelectCallback.filter())
async def select_product(callback: CallbackQuery, callback_data: ProductSelectCallback):
    """Выбор продукта (основной рацион или FMD)"""
    user_id = callback.from_user.id
    product = callback_data.product
    
    if product == "main":
        # Основной рацион
        has_paid = await db.check_payment_status(user_id)
        
        if has_paid:
            # Доступ есть - показываем калории
            await callback.message.edit_text(
                "🔥 <b>Выбери калорийность рациона:</b>\n\n"
                "Доступные варианты от 1200 до 2100 ккал.",
                reply_markup=get_calories_keyboard(),
                parse_mode=ParseMode.HTML
            )
        else:
            # Нет доступа - показываем оплату
            await callback.message.edit_text(
                f"🍽 <b>Рационы питания (14 дней)</b>\n\n"
                f"📋 Включает:\n"
                f"• Завтрак, обед и ужин на каждый день\n"
                f"• Калорийность от 1200 до 2100 ккал\n"
                f"• Подробные рецепты с КБЖУ\n\n"
                f"💰 <b>Стоимость: {PAYMENT_AMOUNT} ₽</b>",
                parse_mode=ParseMode.HTML
            )
            await show_payment_info(callback.message)
    
    elif product == "fmd":
        # FMD Протокол
        has_paid_fmd = await db.check_fmd_payment_status(user_id)
        
        if has_paid_fmd:
            # Доступ есть - показываем дни
            await callback.message.edit_text(
                "🥗 <b>FMD Протокол — Выбери день:</b>\n\n"
                "Программа рассчитана на 5 дней.\n"
                "Выбери день, чтобы посмотреть рецепты.",
                reply_markup=get_fmd_days_keyboard(),
                parse_mode=ParseMode.HTML
            )
        else:
            # Нет доступа - показываем оплату
            await callback.message.edit_text(
                f"🥗 <b>FMD Протокол (5 дней)</b>\n\n"
                f"<i>Fast Mimicking Diet — диета, имитирующая голодание</i>\n\n"
                f"📋 Что это:\n"
                f"• Программа для оздоровления организма\n"
                f"• 5 дней сбалансированного низкокалорийного питания\n"
                f"• Подробные рецепты и список продуктов\n\n"
                f"💰 <b>Стоимость: {FMD_PAYMENT_AMOUNT} ₽</b>",
                parse_mode=ParseMode.HTML
            )
            await show_fmd_payment_info(callback.message)
    
    await callback.answer()


@router.callback_query(BackToProductsCallback.filter())
async def back_to_products(callback: CallbackQuery):
    """Возврат к выбору продукта"""
    user_id = callback.from_user.id
    has_paid = await db.check_payment_status(user_id)
    has_paid_fmd = await db.check_fmd_payment_status(user_id)
    
    await callback.message.edit_text(
        "🍽 <b>Выбери рацион питания:</b>\n\n"
        "📋 <b>Рационы питания (14 дней)</b>\n"
        "Сбалансированное меню на каждый день с калорийностью от 1200 до 2100 ккал.\n\n"
        "🥗 <b>FMD Протокол (5 дней)</b>\n"
        "Диета, имитирующая голодание — программа для оздоровления организма.",
        reply_markup=get_products_keyboard(has_main=has_paid, has_fmd=has_paid_fmd),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


# ==================== FMD Оплата ====================

async def show_fmd_payment_info(message: Message):
    """Показать информацию для оплаты FMD протокола"""
    payment_details = PAYMENT_DETAILS.replace('\\n', '\n')

    await message.answer(
        f"💳 <b>Реквизиты для оплаты FMD Протокола:</b>\n\n"
        f"<code>{payment_details}</code>\n\n"
        f"💰 <b>Сумма: {FMD_PAYMENT_AMOUNT} ₽</b>\n\n"
        "⚠️ <b>ВАЖНО:</b>\n"
        "• Внимательно проверьте реквизиты\n"
        "• После оплаты нажмите кнопку ниже\n"
        "• Проверка занимает до 24 часов",
        reply_markup=get_fmd_payment_keyboard(),
        parse_mode=ParseMode.HTML
    )


@router.callback_query(FMDPaymentCallback.filter())
async def fmd_payment_done(callback: CallbackQuery, bot: Bot, state: FSMContext):
    """Пользователь нажал 'Я оплатил(а)' для FMD - просим скриншот"""
    user = callback.from_user
    
    # Логируем нажатие кнопки
    await db.log_event(user.id, EventType.PAYMENT_BUTTON_CLICKED, "product:fmd")

    # Проверяем, нет ли уже активного запроса на FMD
    has_pending = await db.has_pending_request(user.id, 'fmd')
    if has_pending:
        await callback.answer(
            "⏳ У тебя уже есть запрос на проверке!",
            show_alert=True
        )
        return

    # Проверяем, не оплачено ли уже
    has_paid_fmd = await db.check_fmd_payment_status(user.id)
    if has_paid_fmd:
        await callback.answer(
            "✅ У тебя уже есть доступ к FMD!",
            show_alert=True
        )
        return

    # Устанавливаем состояние ожидания скриншота
    await state.set_state(FMDPaymentState.waiting_for_screenshot)

    await callback.answer()
    await callback.message.answer(
        "📸 <b>Отправь скриншот оплаты FMD Протокола</b>\n\n"
        "Пожалуйста, отправь фото/скриншот подтверждения перевода.\n"
        "Это поможет модераторам быстрее проверить твою оплату.\n\n"
        "⚠️ <i>На скриншоте должны быть видны: сумма, дата и получатель.</i>",
        reply_markup=get_cancel_payment_keyboard(),
        parse_mode=ParseMode.HTML
    )


@router.message(F.text == "❌ Отмена", FMDPaymentState.waiting_for_screenshot)
async def cancel_fmd_payment_screenshot(message: Message, state: FSMContext):
    """Отмена отправки скриншота FMD"""
    await state.clear()
    await message.answer(
        "❌ Отправка отменена.\n\n"
        "Когда будешь готов — нажми кнопку «Я оплатила» снова.",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode=ParseMode.HTML
    )


@router.message(F.photo, FMDPaymentState.waiting_for_screenshot)
async def receive_fmd_payment_screenshot(message: Message, bot: Bot, state: FSMContext):
    """Получение скриншота оплаты FMD и отправка модераторам"""
    user = message.from_user
    
    # Логируем отправку скриншота
    await db.log_event(user.id, EventType.SCREENSHOT_SENT, "product:fmd")

    # Очищаем состояние
    await state.clear()

    # Получаем file_id самого большого фото
    photo = message.photo[-1]
    photo_file_id = photo.file_id

    # Формируем отображение пользователя
    if user.username:
        username_display = f"@{user.username}"
    else:
        full_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or f"User {user.id}"
        username_display = f'<a href="tg://user?id={user.id}">{full_name}</a>'

    # Отправляем фото со скриншотом в канал модераторов
    admin_message = await bot.send_photo(
        chat_id=ADMIN_CHANNEL_ID,
        photo=photo_file_id,
        caption=(
            "🔔 <b>Новый запрос на проверку оплаты FMD!</b>\n\n"
            f"🥗 <b>Продукт: FMD Протокол ({FMD_PAYMENT_AMOUNT} ₽)</b>\n\n"
            f"👤 Пользователь: {username_display}\n"
            f"📝 Имя: {user.first_name or 'Не указано'}\n"
            f"🆔 ID: <code>{user.id}</code>\n\n"
            "Проверьте оплату и выберите действие:"
        ),
        parse_mode=ParseMode.HTML
    )

    # Создаём запрос в БД с типом fmd
    request_id = await db.create_payment_request(user.id, admin_message.message_id, 'fmd')

    # Добавляем кнопки к сообщению админа
    await admin_message.edit_reply_markup(
        reply_markup=get_payment_verification_keyboard(user.id, request_id, 'fmd')
    )

    await message.answer(
        "✅ <b>Запрос отправлен!</b>\n\n"
        "Скриншот оплаты FMD Протокола передан модераторам.\n"
        "Ты получишь уведомление о результате.\n\n"
        "⏳ Обычно проверка занимает до 24 часов.",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode=ParseMode.HTML
    )


@router.message(FMDPaymentState.waiting_for_screenshot)
async def wrong_fmd_payment_content(message: Message):
    """Неверный формат - ожидаем фото для FMD"""
    await message.answer(
        "⚠️ <b>Пожалуйста, отправь фото/скриншот оплаты.</b>\n\n"
        "Если хочешь отменить — нажми кнопку «❌ Отмена».",
        parse_mode=ParseMode.HTML
    )


# ==================== FMD Выбор дней ====================

@router.callback_query(FMDDayCallback.filter())
async def select_fmd_day(callback: CallbackQuery, callback_data: FMDDayCallback):
    """Выбор дня FMD и показ рецептов"""
    # Проверяем доступ
    has_paid_fmd = await db.check_fmd_payment_status(callback.from_user.id)
    if not has_paid_fmd:
        await callback.answer("⛔ Сначала оплати доступ к FMD!", show_alert=True)
        return

    day = callback_data.day
    recipe_text = await get_fmd_recipe_text_async(day)

    # Отправляем новое сообщение с рецептами
    await callback.message.answer(
        recipe_text,
        reply_markup=get_back_to_fmd_days_keyboard(),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@router.callback_query(FMDInfoCallback.filter())
async def show_fmd_info(callback: CallbackQuery, callback_data: FMDInfoCallback):
    """Показ информации о FMD (список продуктов или описание)"""
    # Проверяем доступ
    has_paid_fmd = await db.check_fmd_payment_status(callback.from_user.id)
    if not has_paid_fmd:
        await callback.answer("⛔ Сначала оплати доступ к FMD!", show_alert=True)
        return

    info_type = callback_data.info_type
    
    if info_type == "shopping_list":
        text = get_fmd_shopping_list()
    elif info_type == "about":
        text = get_fmd_info()
    else:
        text = "❌ Информация не найдена"

    await callback.message.answer(
        text,
        reply_markup=get_back_to_fmd_days_keyboard(),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


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
            "Доступные варианты от 1200 до 2100 ккал.",
            reply_markup=get_calories_keyboard(),
            parse_mode=ParseMode.HTML
        )
    elif callback_data.to == "fmd_days":
        await callback.message.edit_text(
            "🥗 <b>FMD Протокол — Выбери день:</b>\n\n"
            "Программа рассчитана на 5 дней.\n"
            "Выбери день, чтобы посмотреть рецепты.",
            reply_markup=get_fmd_days_keyboard(),
            parse_mode=ParseMode.HTML
        )
    await callback.answer()
