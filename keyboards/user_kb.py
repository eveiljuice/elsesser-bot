from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from keyboards.callbacks import (
    PaymentCallback, CaloriesCallback, DayCallback, BackCallback,
    FMDPaymentCallback, FMDDayCallback, ProductSelectCallback, BackToProductsCallback,
    FMDInfoCallback, BundlePaymentCallback
)
from data.recipes import RECIPES, FMD_RECIPES
from config import PAYMENT_AMOUNT, FMD_PAYMENT_AMOUNT


def get_main_menu() -> ReplyKeyboardMarkup:
    """Главное меню с командами"""
    builder = ReplyKeyboardBuilder()
    builder.button(text="🍽 Выбрать рацион")
    builder.button(text="📊 Рассчитать калории")
    builder.button(text="📋 Мой статус")
    builder.button(text="💚 Отдел Заботы")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)


def get_payment_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для оплаты"""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Я оплатила", callback_data=PaymentCallback())
    return builder.as_markup()


def get_fmd_promo_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для промо FMD с кнопкой-командой"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🎁 Хочу сделать себе подарок!", callback_data="/fmd")
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


# ==================== FMD Протокол ====================

def get_fmd_payment_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для оплаты FMD протокола"""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Я оплатила", callback_data=FMDPaymentCallback())
    return builder.as_markup()


def get_bundle_payment_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для оплаты комплекта (Рационы + FMD)"""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Я оплатила", callback_data=BundlePaymentCallback())
    return builder.as_markup()


def get_fmd_days_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора дня FMD протокола"""
    builder = InlineKeyboardBuilder()

    # Информация о FMD и список продуктов
    builder.button(
        text="ℹ️ О протоколе FMD",
        callback_data=FMDInfoCallback(info_type="about")
    )
    builder.button(
        text="🛒 Список продуктов",
        callback_data=FMDInfoCallback(info_type="shopping_list")
    )

    for day in sorted(FMD_RECIPES.keys()):
        builder.button(
            text=f"📅 День {day}",
            callback_data=FMDDayCallback(day=day)
        )

    # Кнопка назад к выбору продукта
    builder.button(
        text="⬅️ Назад",
        callback_data=BackToProductsCallback()
    )

    builder.adjust(2, 3, 2, 1)  # 2 инфо-кнопки, 3 дня, 2 дня, кнопка назад
    return builder.as_markup()


def get_back_to_fmd_days_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с кнопкой 'Назад к дням FMD'"""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="⬅️ Назад к дням FMD",
        callback_data=BackCallback(to="fmd_days")
    )
    return builder.as_markup()


def get_products_keyboard(has_main: bool = False, has_fmd: bool = False, has_bundle: bool = False) -> InlineKeyboardMarkup:
    """Клавиатура выбора продукта (основной рацион, FMD или комплект)

    has_main: True если оплачен основной рацион
    has_fmd: True если оплачен FMD протокол
    has_bundle: True если оплачен комплект
    """
    builder = InlineKeyboardBuilder()

    if has_main:
        builder.button(
            text="🍽 Калькулятор тела (рационы питания) 14 дней ✅",
            callback_data=ProductSelectCallback(product="main")
        )
    else:
        builder.button(
            text=f"🍽 Калькулятор тела (рационы питания) 14 дней — {PAYMENT_AMOUNT} ₽",
            callback_data=ProductSelectCallback(product="main")
        )

    if has_fmd:
        builder.button(
            text="🥗 FMD Протокол (5 дней) ✅",
            callback_data=ProductSelectCallback(product="fmd")
        )
    else:
        builder.button(
            text=f"🥗 FMD Протокол (5 дней) — {FMD_PAYMENT_AMOUNT} ₽",
            callback_data=ProductSelectCallback(product="fmd")
        )

    builder.adjust(1)  # По 1 кнопке в ряд
    return builder.as_markup()
