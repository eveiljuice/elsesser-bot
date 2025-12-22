from aiogram.filters.callback_data import CallbackData


class PaymentCallback(CallbackData, prefix="pay"):
    """Callback для кнопки 'Я оплатил(а)' (основной рацион)"""
    pass


class FMDPaymentCallback(CallbackData, prefix="fmd_pay"):
    """Callback для кнопки 'Я оплатил(а)' (FMD протокол)"""
    pass


class FMDDayCallback(CallbackData, prefix="fmd_day"):
    """Callback для выбора дня FMD протокола"""
    day: int


class FMDInfoCallback(CallbackData, prefix="fmd_info"):
    """Callback для показа информации о FMD"""
    info_type: str  # 'shopping_list' или 'about'


class ProductSelectCallback(CallbackData, prefix="product"):
    """Callback для выбора продукта (рацион или FMD)"""
    product: str  # 'main' или 'fmd'


class BackToProductsCallback(CallbackData, prefix="back_products"):
    """Callback для возврата к выбору продукта"""
    pass


class AdminCallback(CallbackData, prefix="admin"):
    """Callback для админских кнопок подтверждения/отклонения"""
    action: str  # approve / reject
    user_id: int
    request_id: int
    product_type: str = 'main'  # 'main' или 'fmd'


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


# ==================== Calculator Callbacks ====================

class CalcGenderCallback(CallbackData, prefix="calc_gender"):
    """Callback для выбора пола"""
    gender: str  # male / female


class CalcGoalCallback(CallbackData, prefix="calc_goal"):
    """Callback для выбора цели"""
    goal: str  # loss / maintain / gain


class CalcHormonesCallback(CallbackData, prefix="calc_hormones"):
    """Callback для выбора гормональных нарушений"""
    hormones: str  # none / hypothyroidism / insulin / deficiency / other


class CalcLevelCallback(CallbackData, prefix="calc_level"):
    """Callback для выбора уровня"""
    level: str  # amateur / professional


class CalcNavCallback(CallbackData, prefix="calc_nav"):
    """Callback для навигации в калькуляторе"""
    action: str  # next / back / start / restart


class CalcStartCallback(CallbackData, prefix="calc_start"):
    """Callback для запуска калькулятора"""
    pass


class StatsDetailCallback(CallbackData, prefix="stats_detail"):
    """Callback для показа детальной статистики по пользователям"""
    status_type: str  # paid / pending / rejected / only_start / clicked_no_screenshot / all_users


# ==================== Broadcast Management Callbacks ====================

class BroadcastMenuCallback(CallbackData, prefix="bc_menu"):
    """Callback для меню рассылок"""
    action: str  # list / create / back


class BroadcastAudienceCallback(CallbackData, prefix="bc_audience"):
    """Callback для выбора аудитории рассылки"""
    audience: str  # all / start_only / rejected / no_screenshot


class BroadcastConfirmCallback(CallbackData, prefix="bc_confirm"):
    """Callback для подтверждения/отмены рассылки"""
    action: str  # confirm / edit / cancel
    broadcast_id: int = 0


class BroadcastScheduleCallback(CallbackData, prefix="bc_schedule"):
    """Callback для выбора времени отправки"""
    action: str  # now / schedule / set_date / set_time
    value: str = ""


class BroadcastListCallback(CallbackData, prefix="bc_list"):
    """Callback для списка рассылок"""
    action: str  # view / cancel / page
    broadcast_id: int = 0
    page: int = 0


# ==================== Template Management Callbacks ====================

class TemplateMenuCallback(CallbackData, prefix="tpl_menu"):
    """Callback для меню шаблонов"""
    action: str  # list / create / back


class TemplateSelectCallback(CallbackData, prefix="tpl_sel"):
    """Callback для выбора шаблона"""
    action: str  # view / use / use_auto / delete
    template_id: int = 0
    page: int = 0


class TemplateSaveCallback(CallbackData, prefix="tpl_save"):
    """Callback для сохранения рассылки как шаблона"""
    action: str  # confirm / cancel


# ==================== Auto-Broadcast (Trigger) Callbacks ====================

class AutoBroadcastMenuCallback(CallbackData, prefix="auto_menu"):
    """Callback для меню автоматических рассылок"""
    action: str  # list / create / back


class AutoBroadcastTriggerCallback(CallbackData, prefix="auto_trigger"):
    """Callback для выбора триггера автоматической рассылки"""
    trigger: str  # only_start / no_payment / rejected / no_screenshot


class AutoBroadcastDelayCallback(CallbackData, prefix="auto_delay"):
    """Callback для выбора задержки отправки"""
    hours: int


class AutoBroadcastConfirmCallback(CallbackData, prefix="auto_confirm"):
    """Callback для подтверждения автоматической рассылки"""
    action: str  # confirm / edit / cancel


class AutoBroadcastListCallback(CallbackData, prefix="auto_list"):
    """Callback для списка автоматических рассылок"""
    action: str  # view / toggle / delete
    auto_id: int = 0
    page: int = 0