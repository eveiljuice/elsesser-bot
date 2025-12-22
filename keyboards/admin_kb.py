from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from keyboards.callbacks import (
    AdminCallback,
    AdminMenuCallback,
    AdminCaloriesCallback,
    AdminDayCallback,
    AdminMealCallback,
    AdminEditCallback,
    StatsDetailCallback,
    BroadcastMenuCallback,
    BroadcastAudienceCallback,
    BroadcastConfirmCallback,
    BroadcastScheduleCallback,
    BroadcastListCallback,
    TemplateMenuCallback,
    TemplateSelectCallback,
    TemplateSaveCallback,
    AutoBroadcastMenuCallback,
    AutoBroadcastTriggerCallback,
    AutoBroadcastDelayCallback,
    AutoBroadcastConfirmCallback,
    AutoBroadcastListCallback
)
from data.recipes import RECIPES


def get_payment_verification_keyboard(user_id: int, request_id: int, product_type: str = 'main') -> InlineKeyboardMarkup:
    """Клавиатура для админов: подтвердить/отклонить оплату
    
    product_type: 'main' - основной рацион, 'fmd' - FMD протокол
    """
    builder = InlineKeyboardBuilder()

    builder.button(
        text="✅ Подтвердить",
        callback_data=AdminCallback(
            action="approve", user_id=user_id, request_id=request_id, product_type=product_type)
    )
    builder.button(
        text="❌ Отклонить",
        callback_data=AdminCallback(
            action="reject", user_id=user_id, request_id=request_id, product_type=product_type)
    )

    builder.adjust(2)
    return builder.as_markup()


# ==================== Admin Content Management ====================

def get_admin_main_menu() -> ReplyKeyboardMarkup:
    """Главное меню админки"""
    builder = ReplyKeyboardBuilder()
    builder.button(text="📝 Редактировать рационы")
    builder.button(text="📊 Статистика")
    builder.button(text="📣 Управление рассылками")
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


def get_stats_detail_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для просмотра детальной статистики по пользователям"""
    builder = InlineKeyboardBuilder()
    
    builder.button(
        text="💰 Оплатили",
        callback_data=StatsDetailCallback(status_type="paid")
    )
    builder.button(
        text="⏳ Ожидают проверки",
        callback_data=StatsDetailCallback(status_type="pending")
    )
    builder.button(
        text="❌ Отклонены",
        callback_data=StatsDetailCallback(status_type="rejected")
    )
    builder.button(
        text="😴 Только /start",
        callback_data=StatsDetailCallback(status_type="only_start")
    )
    builder.button(
        text="🤔 Нажали оплату без скрина",
        callback_data=StatsDetailCallback(status_type="clicked_no_screenshot")
    )
    builder.button(
        text="👥 Все пользователи",
        callback_data=StatsDetailCallback(status_type="all_users")
    )
    
    builder.adjust(2)
    return builder.as_markup()


# ==================== Broadcast Management Keyboards ====================

def get_broadcast_menu_keyboard() -> InlineKeyboardMarkup:
    """Главное меню рассылок"""
    builder = InlineKeyboardBuilder()
    
    builder.button(
        text="➕ Создать рассылку",
        callback_data=BroadcastMenuCallback(action="create")
    )
    builder.button(
        text="📋 Запланированные рассылки",
        callback_data=BroadcastMenuCallback(action="list")
    )
    builder.button(
        text="📁 Шаблоны рассылок",
        callback_data=TemplateMenuCallback(action="list")
    )
    builder.button(
        text="🤖 Автоматические рассылки",
        callback_data=AutoBroadcastMenuCallback(action="list")
    )
    
    builder.adjust(1)
    return builder.as_markup()


def get_broadcast_audience_keyboard() -> InlineKeyboardMarkup:
    """Выбор аудитории для рассылки"""
    builder = InlineKeyboardBuilder()
    
    builder.button(
        text="👥 Всем пользователям",
        callback_data=BroadcastAudienceCallback(audience="all")
    )
    builder.button(
        text="👆 Только /start (ничего не делали)",
        callback_data=BroadcastAudienceCallback(audience="start_only")
    )
    builder.button(
        text="❌ Отклонённые оплаты",
        callback_data=BroadcastAudienceCallback(audience="rejected")
    )
    builder.button(
        text="🤔 Нажали оплату без скрина",
        callback_data=BroadcastAudienceCallback(audience="no_screenshot")
    )
    builder.button(
        text="⬅️ Назад",
        callback_data=BroadcastMenuCallback(action="back")
    )
    
    builder.adjust(1)
    return builder.as_markup()


def get_broadcast_schedule_keyboard() -> InlineKeyboardMarkup:
    """Выбор времени отправки"""
    builder = InlineKeyboardBuilder()
    
    builder.button(
        text="🚀 Отправить сейчас",
        callback_data=BroadcastScheduleCallback(action="now")
    )
    builder.button(
        text="📅 Запланировать",
        callback_data=BroadcastScheduleCallback(action="schedule")
    )
    builder.button(
        text="✏️ Изменить текст",
        callback_data=BroadcastConfirmCallback(action="edit")
    )
    builder.button(
        text="❌ Отменить",
        callback_data=BroadcastConfirmCallback(action="cancel")
    )
    
    builder.adjust(2)
    return builder.as_markup()


def get_broadcast_confirm_keyboard(broadcast_id: int = 0) -> InlineKeyboardMarkup:
    """Финальное подтверждение рассылки"""
    builder = InlineKeyboardBuilder()
    
    builder.button(
        text="✅ Подтвердить отправку",
        callback_data=BroadcastConfirmCallback(action="confirm", broadcast_id=broadcast_id)
    )
    builder.button(
        text="✏️ Изменить текст",
        callback_data=BroadcastConfirmCallback(action="edit", broadcast_id=broadcast_id)
    )
    builder.button(
        text="❌ Отменить рассылку",
        callback_data=BroadcastConfirmCallback(action="cancel", broadcast_id=broadcast_id)
    )
    
    builder.adjust(1)
    return builder.as_markup()


def get_broadcast_list_keyboard(broadcasts: list, page: int = 0, per_page: int = 5) -> InlineKeyboardMarkup:
    """Список запланированных рассылок с пагинацией"""
    builder = InlineKeyboardBuilder()
    
    start_idx = page * per_page
    end_idx = start_idx + per_page
    page_broadcasts = broadcasts[start_idx:end_idx]
    
    for bc in page_broadcasts:
        # Формируем краткое описание
        audience_names = {
            'all': '👥 Все',
            'start_only': '👆 /start',
            'rejected': '❌ Откл.',
            'no_screenshot': '🤔 Без скр.'
        }
        audience = audience_names.get(bc.get('audience', 'all'), '👥')
        scheduled = bc.get('scheduled_at', '')[:16].replace('T', ' ')
        
        builder.button(
            text=f"📨 {scheduled} | {audience}",
            callback_data=BroadcastListCallback(action="view", broadcast_id=bc['id'])
        )
    
    # Пагинация
    nav_buttons = []
    if page > 0:
        builder.button(
            text="◀️ Назад",
            callback_data=BroadcastListCallback(action="page", page=page - 1)
        )
    if end_idx < len(broadcasts):
        builder.button(
            text="Вперёд ▶️",
            callback_data=BroadcastListCallback(action="page", page=page + 1)
        )
    
    builder.button(
        text="🔙 В меню рассылок",
        callback_data=BroadcastMenuCallback(action="back")
    )
    
    # Adjust: сначала рассылки по одной, затем навигация
    rows = [1] * len(page_broadcasts)
    if page > 0 and end_idx < len(broadcasts):
        rows.append(2)  # Обе кнопки навигации
    elif page > 0 or end_idx < len(broadcasts):
        rows.append(1)  # Одна кнопка навигации
    rows.append(1)  # Кнопка "В меню"
    
    builder.adjust(*rows)
    return builder.as_markup()


def get_broadcast_view_keyboard(broadcast_id: int) -> InlineKeyboardMarkup:
    """Просмотр конкретной рассылки"""
    builder = InlineKeyboardBuilder()
    
    builder.button(
        text="❌ Отменить рассылку",
        callback_data=BroadcastListCallback(action="cancel", broadcast_id=broadcast_id)
    )
    builder.button(
        text="⬅️ К списку",
        callback_data=BroadcastMenuCallback(action="list")
    )
    
    builder.adjust(1)
    return builder.as_markup()


# ==================== Template Management Keyboards ====================

def get_template_menu_keyboard() -> InlineKeyboardMarkup:
    """Меню шаблонов рассылок"""
    builder = InlineKeyboardBuilder()
    
    builder.button(
        text="➕ Создать шаблон",
        callback_data=TemplateMenuCallback(action="create")
    )
    builder.button(
        text="📋 Мои шаблоны",
        callback_data=TemplateMenuCallback(action="list")
    )
    builder.button(
        text="⬅️ Назад",
        callback_data=BroadcastMenuCallback(action="back")
    )
    
    builder.adjust(1)
    return builder.as_markup()


def get_template_list_keyboard(templates: list, page: int = 0, per_page: int = 5) -> InlineKeyboardMarkup:
    """Список шаблонов с пагинацией"""
    builder = InlineKeyboardBuilder()
    
    start_idx = page * per_page
    end_idx = start_idx + per_page
    page_templates = templates[start_idx:end_idx]
    
    for tpl in page_templates:
        # Первые 30 символов текста как название
        preview = tpl.get('content', '')[:30].replace('\n', ' ')
        if len(tpl.get('content', '')) > 30:
            preview += "..."
        
        builder.button(
            text=f"📄 {tpl.get('name', preview)}",
            callback_data=TemplateSelectCallback(action="view", template_id=tpl['id'])
        )
    
    # Пагинация
    if page > 0:
        builder.button(
            text="◀️ Назад",
            callback_data=TemplateSelectCallback(action="view", template_id=0, page=page - 1)
        )
    if end_idx < len(templates):
        builder.button(
            text="Вперёд ▶️",
            callback_data=TemplateSelectCallback(action="view", template_id=0, page=page + 1)
        )
    
    builder.button(
        text="🔙 В меню шаблонов",
        callback_data=TemplateMenuCallback(action="back")
    )
    
    # Adjust
    rows = [1] * len(page_templates)
    if page > 0 and end_idx < len(templates):
        rows.append(2)
    elif page > 0 or end_idx < len(templates):
        rows.append(1)
    rows.append(1)
    
    builder.adjust(*rows)
    return builder.as_markup()


def get_template_view_keyboard(template_id: int) -> InlineKeyboardMarkup:
    """Просмотр конкретного шаблона"""
    builder = InlineKeyboardBuilder()
    
    builder.button(
        text="📨 Использовать для рассылки",
        callback_data=TemplateSelectCallback(action="use", template_id=template_id)
    )
    builder.button(
        text="🤖 Использовать для авто-рассылки",
        callback_data=TemplateSelectCallback(action="use_auto", template_id=template_id)
    )
    builder.button(
        text="🗑 Удалить шаблон",
        callback_data=TemplateSelectCallback(action="delete", template_id=template_id)
    )
    builder.button(
        text="⬅️ К списку",
        callback_data=TemplateMenuCallback(action="list")
    )
    
    builder.adjust(1)
    return builder.as_markup()


def get_template_save_keyboard() -> InlineKeyboardMarkup:
    """Кнопка сохранения рассылки как шаблона"""
    builder = InlineKeyboardBuilder()
    
    builder.button(
        text="💾 Сохранить как шаблон",
        callback_data=TemplateSaveCallback(action="confirm")
    )
    builder.button(
        text="❌ Не сохранять",
        callback_data=TemplateSaveCallback(action="cancel")
    )
    
    builder.adjust(2)
    return builder.as_markup()


# ==================== Auto-Broadcast Keyboards ====================

def get_auto_broadcast_menu_keyboard() -> InlineKeyboardMarkup:
    """Меню автоматических рассылок"""
    builder = InlineKeyboardBuilder()
    
    builder.button(
        text="➕ Создать авто-рассылку",
        callback_data=AutoBroadcastMenuCallback(action="create")
    )
    builder.button(
        text="📋 Активные авто-рассылки",
        callback_data=AutoBroadcastMenuCallback(action="list")
    )
    builder.button(
        text="⬅️ Назад",
        callback_data=BroadcastMenuCallback(action="back")
    )
    
    builder.adjust(1)
    return builder.as_markup()


def get_auto_broadcast_trigger_keyboard() -> InlineKeyboardMarkup:
    """Выбор триггера для автоматической рассылки"""
    builder = InlineKeyboardBuilder()
    
    builder.button(
        text="👆 Только /start (ничего не делали)",
        callback_data=AutoBroadcastTriggerCallback(trigger="only_start")
    )
    builder.button(
        text="💳 Не оплатили (после клика оплатить)",
        callback_data=AutoBroadcastTriggerCallback(trigger="no_payment")
    )
    builder.button(
        text="❌ Отклонённая оплата",
        callback_data=AutoBroadcastTriggerCallback(trigger="rejected")
    )
    builder.button(
        text="🤔 Нажали оплатить без скрина",
        callback_data=AutoBroadcastTriggerCallback(trigger="no_screenshot")
    )
    builder.button(
        text="⬅️ Назад",
        callback_data=AutoBroadcastMenuCallback(action="back")
    )
    
    builder.adjust(1)
    return builder.as_markup()


def get_auto_broadcast_delay_keyboard() -> InlineKeyboardMarkup:
    """Выбор задержки отправки автоматической рассылки"""
    builder = InlineKeyboardBuilder()
    
    delays = [
        (1, "1 час"),
        (2, "2 часа"),
        (6, "6 часов"),
        (12, "12 часов"),
        (24, "24 часа"),
        (48, "48 часов"),
        (72, "3 дня"),
    ]
    
    for hours, text in delays:
        builder.button(
            text=f"⏰ {text}",
            callback_data=AutoBroadcastDelayCallback(hours=hours)
        )
    
    builder.button(
        text="⬅️ Назад",
        callback_data=AutoBroadcastMenuCallback(action="create")
    )
    
    builder.adjust(2, 2, 2, 1, 1)
    return builder.as_markup()


def get_auto_broadcast_audience_keyboard() -> InlineKeyboardMarkup:
    """Выбор аудитории для автоматической рассылки"""
    builder = InlineKeyboardBuilder()
    
    builder.button(
        text="👥 Всем пользователям (совпавшим с триггером)",
        callback_data=BroadcastAudienceCallback(audience="all")
    )
    builder.button(
        text="⬅️ Назад",
        callback_data=AutoBroadcastMenuCallback(action="create")
    )
    
    builder.adjust(1)
    return builder.as_markup()


def get_auto_broadcast_confirm_keyboard() -> InlineKeyboardMarkup:
    """Подтверждение создания автоматической рассылки"""
    builder = InlineKeyboardBuilder()
    
    builder.button(
        text="✅ Создать авто-рассылку",
        callback_data=AutoBroadcastConfirmCallback(action="confirm")
    )
    builder.button(
        text="✏️ Изменить текст",
        callback_data=AutoBroadcastConfirmCallback(action="edit")
    )
    builder.button(
        text="❌ Отменить",
        callback_data=AutoBroadcastConfirmCallback(action="cancel")
    )
    
    builder.adjust(1)
    return builder.as_markup()


def get_auto_broadcast_list_keyboard(auto_broadcasts: list, page: int = 0, per_page: int = 5) -> InlineKeyboardMarkup:
    """Список автоматических рассылок с пагинацией"""
    builder = InlineKeyboardBuilder()
    
    trigger_names = {
        'only_start': '👆 /start',
        'no_payment': '💳 Не оплат.',
        'rejected': '❌ Откл.',
        'no_screenshot': '🤔 Без скр.'
    }
    
    start_idx = page * per_page
    end_idx = start_idx + per_page
    page_items = auto_broadcasts[start_idx:end_idx]
    
    for ab in page_items:
        trigger = trigger_names.get(ab.get('trigger_type', ''), '?')
        status = "🟢" if ab.get('is_active', False) else "🔴"
        delay = ab.get('delay_hours', 0)
        
        builder.button(
            text=f"{status} {trigger} | {delay}ч",
            callback_data=AutoBroadcastListCallback(action="view", auto_id=ab['id'])
        )
    
    # Пагинация
    if page > 0:
        builder.button(
            text="◀️ Назад",
            callback_data=AutoBroadcastListCallback(action="view", auto_id=0, page=page - 1)
        )
    if end_idx < len(auto_broadcasts):
        builder.button(
            text="Вперёд ▶️",
            callback_data=AutoBroadcastListCallback(action="view", auto_id=0, page=page + 1)
        )
    
    builder.button(
        text="🔙 В меню авто-рассылок",
        callback_data=AutoBroadcastMenuCallback(action="back")
    )
    
    # Adjust
    rows = [1] * len(page_items)
    if page > 0 and end_idx < len(auto_broadcasts):
        rows.append(2)
    elif page > 0 or end_idx < len(auto_broadcasts):
        rows.append(1)
    rows.append(1)
    
    builder.adjust(*rows)
    return builder.as_markup()


def get_auto_broadcast_view_keyboard(auto_id: int, is_active: bool) -> InlineKeyboardMarkup:
    """Просмотр конкретной автоматической рассылки"""
    builder = InlineKeyboardBuilder()
    
    if is_active:
        builder.button(
            text="⏸ Приостановить",
            callback_data=AutoBroadcastListCallback(action="toggle", auto_id=auto_id)
        )
    else:
        builder.button(
            text="▶️ Активировать",
            callback_data=AutoBroadcastListCallback(action="toggle", auto_id=auto_id)
        )
    
    builder.button(
        text="🗑 Удалить",
        callback_data=AutoBroadcastListCallback(action="delete", auto_id=auto_id)
    )
    builder.button(
        text="⬅️ К списку",
        callback_data=AutoBroadcastMenuCallback(action="list")
    )
    
    builder.adjust(1)
    return builder.as_markup()


def get_skip_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура с кнопкой 'Пропустить'"""
    builder = ReplyKeyboardBuilder()
    builder.button(text="⏭ Пропустить")
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True)
