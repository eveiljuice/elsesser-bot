from aiogram.filters.callback_data import CallbackData


class PaymentCallback(CallbackData, prefix="pay"):
    """Callback для кнопки 'Я оплатил(а)' (основной рацион)"""
    pass


class FMDPaymentCallback(CallbackData, prefix="fmd_pay"):
    """Callback для кнопки 'Я оплатил(а)' (FMD протокол)"""
    pass


class BundlePaymentCallback(CallbackData, prefix="bundle_pay"):
    """Callback для кнопки 'Я оплатил(а)' (Комплект: Рационы + FMD)"""
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


# ==================== Broadcast Chain (Funnel) Callbacks ====================

class ChainMenuCallback(CallbackData, prefix="chain_menu"):
    """Callback для меню цепочек рассылок"""
    action: str  # list / create / back


class ChainListCallback(CallbackData, prefix="chain_list"):
    """Callback для списка цепочек"""
    action: str  # view / toggle / delete
    chain_id: int = 0
    page: int = 0


class ChainEditCallback(CallbackData, prefix="chain_edit"):
    """Callback для редактирования цепочки"""
    action: str  # add_step / edit_step / delete_step / view_steps / start_send / back
    chain_id: int = 0
    step_id: int = 0


class ChainStepCallback(CallbackData, prefix="chain_step"):
    """Callback для работы с шагами цепочки"""
    action: str  # view / edit / add_button / delete_button / back
    step_id: int = 0
    button_id: int = 0


class ChainButtonActionCallback(CallbackData, prefix="chain_btn_action"):
    """Callback для выбора действия кнопки в шаге"""
    action_type: str  # next_step / goto_step / url / command / stop_chain / payment_main / payment_fmd / payment_bundle


class ChainTriggerCallback(CallbackData, prefix="chain_trigger"):
    """Callback для выбора триггера запуска цепочки"""
    trigger: str  # manual / subscription_end / payment_approved / custom


class ChainAudienceCallback(CallbackData, prefix="chain_audience"):
    """Callback для выбора аудитории для ручного запуска цепочки"""
    audience: str  # all / start_only / paid / not_paid / custom


class ChainUserButtonCallback(CallbackData, prefix="cub"):
    """Callback для кнопок в сообщениях цепочки (для пользователей)
    Prefix короткий чтобы вместить больше данных
    """
    chain_id: int
    step_id: int
    button_id: int


# ==================== User Management Callbacks ====================

class UserManageMenuCallback(CallbackData, prefix="user_menu"):
    """Callback для меню управления пользователями"""
    action: str  # list_all / list_paid / search / back


class UserListCallback(CallbackData, prefix="user_list"):
    """Callback для списка пользователей"""
    action: str  # view / page
    user_id: int = 0
    page: int = 0
    payment_filter: str = "all"  # all / paid_main / paid_fmd / paid_bundle


class UserActionCallback(CallbackData, prefix="user_act"):
    """Callback для действий над пользователем"""
    action: str  # reset_main / reset_fmd / reset_bundle / reset_all / view / back
    user_id: int


# ==================== Support (Отдел Заботы) Callbacks ====================

class SupportReplyCallback(CallbackData, prefix="support"):
    """Callback для ответа модератора на вопрос пользователя"""
    action: str  # reply
    user_id: int
    question_id: int