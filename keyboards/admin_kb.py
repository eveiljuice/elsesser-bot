from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from keyboards.callbacks import (
    AdminCallback,
    AdminMenuCallback,
    AdminCaloriesCallback,
    AdminDayCallback,
    AdminMealCallback,
    AdminEditCallback
)
from data.recipes import RECIPES


def get_payment_verification_keyboard(user_id: int, request_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для админов: подтвердить/отклонить оплату"""
    builder = InlineKeyboardBuilder()

    builder.button(
        text="✅ Подтвердить",
        callback_data=AdminCallback(
            action="approve", user_id=user_id, request_id=request_id)
    )
    builder.button(
        text="❌ Отклонить",
        callback_data=AdminCallback(
            action="reject", user_id=user_id, request_id=request_id)
    )

    builder.adjust(2)
    return builder.as_markup()


# ==================== Admin Content Management ====================

def get_admin_main_menu() -> ReplyKeyboardMarkup:
    """Главное меню админки"""
    builder = ReplyKeyboardBuilder()
    builder.button(text="📝 Редактировать рационы")
    builder.button(text="📊 Статистика")
    builder.button(text="📬 Отправить недельный отчёт")
    builder.button(text="🔙 Выйти из админки")
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True)


def get_admin_calories_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора калорийности для админки"""
    builder = InlineKeyboardBuilder()

    calories_list = sorted(RECIPES.keys())
    for cal in calories_list:
        builder.button(
            text=f"🔥 {cal} ккал",
            callback_data=AdminCaloriesCallback(calories=cal)
        )

    builder.adjust(2)
    return builder.as_markup()


def get_admin_days_keyboard(calories: int) -> InlineKeyboardMarkup:
    """Клавиатура выбора дня для админки"""
    builder = InlineKeyboardBuilder()

    days = RECIPES.get(calories, {})
    for day in sorted(days.keys()):
        builder.button(
            text=f"📅 День {day}",
            callback_data=AdminDayCallback(calories=calories, day=day)
        )

    # Кнопка назад
    builder.button(
        text="⬅️ Назад",
        callback_data=AdminMenuCallback(action="back")
    )

    days_count = len(days)
    if days_count <= 3:
        builder.adjust(days_count, 1)
    elif days_count == 4:
        builder.adjust(2, 2, 1)
    else:
        builder.adjust(3, 3, 1)

    return builder.as_markup()


def get_admin_meals_keyboard(calories: int, day: int) -> InlineKeyboardMarkup:
    """Клавиатура выбора приёма пищи для админки"""
    builder = InlineKeyboardBuilder()

    meals = [
        ("🌅 Завтрак", "breakfast"),
        ("🍽 Обед", "lunch"),
        ("🌙 Ужин", "dinner"),
    ]

    for text, meal in meals:
        builder.button(
            text=text,
            callback_data=AdminMealCallback(
                calories=calories, day=day, meal=meal)
        )

    builder.button(
        text="⬅️ Назад к дням",
        callback_data=AdminCaloriesCallback(calories=calories)
    )

    builder.adjust(3, 1)
    return builder.as_markup()


def get_admin_edit_keyboard(calories: int, day: int, meal: str) -> InlineKeyboardMarkup:
    """Клавиатура действий редактирования"""
    builder = InlineKeyboardBuilder()

    builder.button(
        text="✏️ Редактировать",
        callback_data=AdminEditCallback(
            action="edit", calories=calories, day=day, meal=meal)
    )
    builder.button(
        text="👁 Превью",
        callback_data=AdminEditCallback(
            action="preview", calories=calories, day=day, meal=meal)
    )
    builder.button(
        text="🔄 Сбросить к исходному",
        callback_data=AdminEditCallback(
            action="reset", calories=calories, day=day, meal=meal)
    )
    builder.button(
        text="⬅️ Назад к приёмам пищи",
        callback_data=AdminDayCallback(calories=calories, day=day)
    )

    builder.adjust(2, 1, 1)
    return builder.as_markup()


def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура отмены"""
    builder = ReplyKeyboardBuilder()
    builder.button(text="❌ Отмена")
    return builder.as_markup(resize_keyboard=True)
