"""Клавиатуры для калькулятора калорий"""

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from keyboards.callbacks import (
    CalcGenderCallback,
    CalcGoalCallback,
    CalcHormonesCallback,
    CalcLevelCallback,
    CalcNavCallback,
    CalcStartCallback,
)


def get_start_calculator_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для запуска калькулятора"""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="📊 Рассчитать калории",
        callback_data=CalcStartCallback()
    )
    return builder.as_markup()


def get_gender_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора пола (Страница 1/5)"""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="👩 Женский",
        callback_data=CalcGenderCallback(gender="female")
    )
    builder.button(
        text="👨 Мужской",
        callback_data=CalcGenderCallback(gender="male")
    )
    builder.adjust(1)
    return builder.as_markup()


def get_goal_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора цели (Страница 3/5)"""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="🔻 Похудение",
        callback_data=CalcGoalCallback(goal="loss")
    )
    builder.button(
        text="⚖️ Сохранение веса / Рекомпозиция",
        callback_data=CalcGoalCallback(goal="maintain")
    )
    builder.button(
        text="💪 Набор веса / мышечной массы",
        callback_data=CalcGoalCallback(goal="gain")
    )
    # Кнопка назад
    builder.button(
        text="⬅️ Назад",
        callback_data=CalcNavCallback(action="back_to_step2")
    )
    builder.adjust(1)
    return builder.as_markup()


def get_hormones_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора гормональных нарушений (Страница 3/5)"""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✅ Нет / Никогда не сдавал анализы",
        callback_data=CalcHormonesCallback(hormones="none")
    )
    builder.button(
        text="🔹 Гипотиреоз",
        callback_data=CalcHormonesCallback(hormones="hypothyroidism")
    )
    builder.button(
        text="🔹 Лептинорезистентность/Инсулинорезистентность",
        callback_data=CalcHormonesCallback(hormones="insulin")
    )
    builder.button(
        text="🔹 Дефициты половых гормонов",
        callback_data=CalcHormonesCallback(hormones="deficiency")
    )
    builder.button(
        text="🔹 Различные эндокринные нарушения",
        callback_data=CalcHormonesCallback(hormones="other")
    )
    builder.adjust(1)
    return builder.as_markup()


def get_level_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора уровня (Страница 4/5)"""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="🏃 Любительский",
        callback_data=CalcLevelCallback(level="amateur")
    )
    builder.button(
        text="🏆 Профессиональный / выступающий спортсмен",
        callback_data=CalcLevelCallback(level="professional")
    )
    # Кнопка назад
    builder.button(
        text="⬅️ Назад",
        callback_data=CalcNavCallback(action="back_to_step3")
    )
    builder.adjust(1)
    return builder.as_markup()


def get_step1_nav_keyboard() -> InlineKeyboardMarkup:
    """Навигация для страницы 1 (ввод возраста/роста/веса)"""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Вперёд →",
        callback_data=CalcNavCallback(action="to_step2")
    )
    builder.adjust(1)
    return builder.as_markup()


def get_step2_nav_keyboard() -> InlineKeyboardMarkup:
    """Навигация для страницы 2 (шаги/тренировки)"""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="⬅️ Назад",
        callback_data=CalcNavCallback(action="back_to_step1")
    )
    builder.button(
        text="Вперёд →",
        callback_data=CalcNavCallback(action="to_step3")
    )
    builder.adjust(2)
    return builder.as_markup()


def get_results_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура на странице результатов"""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="🔄 Пересчитать",
        callback_data=CalcNavCallback(action="restart")
    )
    builder.button(
        text="🍽 Выбрать рацион",
        callback_data=CalcNavCallback(action="to_rations")
    )
    builder.adjust(1)
    return builder.as_markup()
