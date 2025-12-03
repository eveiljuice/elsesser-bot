from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from keyboards.callbacks import PaymentCallback, CaloriesCallback, DayCallback, BackCallback
from data.recipes import RECIPES


def get_main_menu() -> ReplyKeyboardMarkup:
    """Главное меню с командами"""
    builder = ReplyKeyboardBuilder()
    builder.button(text="🍽 Выбрать рацион")
    builder.button(text="📊 Рассчитать калории")
    builder.button(text="📋 Мой статус")
    builder.button(text="❓ Помощь")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)


def get_payment_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для оплаты"""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Я оплатил(а)", callback_data=PaymentCallback())
    return builder.as_markup()


def get_calories_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора калорийности"""
    builder = InlineKeyboardBuilder()

    calories_list = sorted(RECIPES.keys())
    for cal in calories_list:
        builder.button(
            text=f"🔥 {cal} ккал",
            callback_data=CaloriesCallback(calories=cal)
        )

    builder.adjust(2)  # По 2 кнопки в ряд
    return builder.as_markup()


def get_days_keyboard(calories: int) -> InlineKeyboardMarkup:
    """Клавиатура выбора дня для конкретной калорийности"""
    builder = InlineKeyboardBuilder()

    days = RECIPES.get(calories, {})
    for day in sorted(days.keys()):
        builder.button(
            text=f"📅 День {day}",
            callback_data=DayCallback(calories=calories, day=day)
        )

    # Кнопка назад
    builder.button(
        text="⬅️ Назад к калориям",
        callback_data=BackCallback(to="calories")
    )

    # Дни по 3 в ряд, кнопка назад отдельно
    days_count = len(days)
    if days_count <= 3:
        builder.adjust(days_count, 1)
    elif days_count == 4:
        builder.adjust(2, 2, 1)
    else:
        builder.adjust(3, 3, 1)

    return builder.as_markup()


def get_back_to_calories_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с кнопкой 'Назад к калориям'"""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="⬅️ Назад к калориям",
        callback_data=BackCallback(to="calories")
    )
    return builder.as_markup()
