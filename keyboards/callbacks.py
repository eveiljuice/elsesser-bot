from aiogram.filters.callback_data import CallbackData


class PaymentCallback(CallbackData, prefix="pay"):
    """Callback для кнопки 'Я оплатил(а)'"""
    pass


class AdminCallback(CallbackData, prefix="admin"):
    """Callback для админских кнопок подтверждения/отклонения"""
    action: str  # approve / reject
    user_id: int
    request_id: int


class CaloriesCallback(CallbackData, prefix="cal"):
    """Callback для выбора калорийности"""
    calories: int


class DayCallback(CallbackData, prefix="day"):
    """Callback для выбора дня"""
    calories: int
    day: int


class BackCallback(CallbackData, prefix="back"):
    """Callback для кнопки 'Назад'"""
    to: str  # calories / main


# ==================== Admin Content Editing ====================

class AdminMenuCallback(CallbackData, prefix="adm_menu"):
    """Callback для главного админ меню"""
    action: str  # edit_content / back


class AdminCaloriesCallback(CallbackData, prefix="adm_cal"):
    """Callback для выбора калорийности в админке"""
    calories: int


class AdminDayCallback(CallbackData, prefix="adm_day"):
    """Callback для выбора дня в админке"""
    calories: int
    day: int


class AdminMealCallback(CallbackData, prefix="adm_meal"):
    """Callback для выбора приёма пищи в админке"""
    calories: int
    day: int
    meal: str  # breakfast / lunch / dinner


class AdminEditCallback(CallbackData, prefix="adm_edit"):
    """Callback для действий редактирования"""
    action: str  # edit / preview / reset / back
    calories: int
    day: int
    meal: str
