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
    AutoBroadcastListCallback,
    ChainMenuCallback,
    ChainListCallback,
    ChainEditCallback,
    ChainStepCallback,
    ChainButtonActionCallback,
    ChainTriggerCallback,
    ChainAudienceCallback,
    ChainUserButtonCallback,
    UserManageMenuCallback,
    UserListCallback,
    UserActionCallback,
    SupportReplyCallback
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
    builder.button(text="👥 Управление пользователями")
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
    builder.button(
        text="🔗 Цепочки рассылок",
        callback_data=ChainMenuCallback(action="list")
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
        callback_data=BroadcastConfirmCallback(
            action="confirm", broadcast_id=broadcast_id)
    )
    builder.button(
        text="✏️ Изменить текст",
        callback_data=BroadcastConfirmCallback(
            action="edit", broadcast_id=broadcast_id)
    )
    builder.button(
        text="❌ Отменить рассылку",
        callback_data=BroadcastConfirmCallback(
            action="cancel", broadcast_id=broadcast_id)
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
            callback_data=BroadcastListCallback(
                action="view", broadcast_id=bc['id'])
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
        callback_data=BroadcastListCallback(
            action="cancel", broadcast_id=broadcast_id)
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
            callback_data=TemplateSelectCallback(
                action="view", template_id=tpl['id'])
        )

    # Пагинация
    if page > 0:
        builder.button(
            text="◀️ Назад",
            callback_data=TemplateSelectCallback(
                action="view", template_id=0, page=page - 1)
        )
    if end_idx < len(templates):
        builder.button(
            text="Вперёд ▶️",
            callback_data=TemplateSelectCallback(
                action="view", template_id=0, page=page + 1)
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
        callback_data=TemplateSelectCallback(
            action="use", template_id=template_id)
    )
    builder.button(
        text="🤖 Использовать для авто-рассылки",
        callback_data=TemplateSelectCallback(
            action="use_auto", template_id=template_id)
    )
    builder.button(
        text="🗑 Удалить шаблон",
        callback_data=TemplateSelectCallback(
            action="delete", template_id=template_id)
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
            callback_data=AutoBroadcastListCallback(
                action="view", auto_id=ab['id'])
        )

    # Пагинация
    if page > 0:
        builder.button(
            text="◀️ Назад",
            callback_data=AutoBroadcastListCallback(
                action="view", auto_id=0, page=page - 1)
        )
    if end_idx < len(auto_broadcasts):
        builder.button(
            text="Вперёд ▶️",
            callback_data=AutoBroadcastListCallback(
                action="view", auto_id=0, page=page + 1)
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
            callback_data=AutoBroadcastListCallback(
                action="toggle", auto_id=auto_id)
        )
    else:
        builder.button(
            text="▶️ Активировать",
            callback_data=AutoBroadcastListCallback(
                action="toggle", auto_id=auto_id)
        )

    builder.button(
        text="🗑 Удалить",
        callback_data=AutoBroadcastListCallback(
            action="delete", auto_id=auto_id)
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


# ==================== Broadcast Chain Keyboards ====================

def get_chain_menu_keyboard() -> InlineKeyboardMarkup:
    """Меню цепочек рассылок"""
    builder = InlineKeyboardBuilder()

    builder.button(
        text="➕ Создать цепочку",
        callback_data=ChainMenuCallback(action="create")
    )
    builder.button(
        text="📋 Мои цепочки",
        callback_data=ChainListCallback(action="view", chain_id=0)
    )
    builder.button(
        text="⬅️ Назад",
        callback_data=BroadcastMenuCallback(action="back")
    )

    builder.adjust(1)
    return builder.as_markup()


def get_chain_trigger_keyboard() -> InlineKeyboardMarkup:
    """Выбор триггера для цепочки"""
    builder = InlineKeyboardBuilder()

    builder.button(
        text="✋ Ручной запуск",
        callback_data=ChainTriggerCallback(trigger="manual")
    )
    builder.button(
        text="⏰ Конец подписки (через 30 дней)",
        callback_data=ChainTriggerCallback(trigger="subscription_end")
    )
    builder.button(
        text="✅ После оплаты",
        callback_data=ChainTriggerCallback(trigger="payment_approved")
    )
    builder.button(
        text="⬅️ Назад",
        callback_data=ChainMenuCallback(action="back")
    )

    builder.adjust(1)
    return builder.as_markup()


def get_chain_list_keyboard(chains: list, page: int = 0, per_page: int = 5) -> InlineKeyboardMarkup:
    """Список цепочек с пагинацией"""
    builder = InlineKeyboardBuilder()

    start_idx = page * per_page
    end_idx = start_idx + per_page
    page_chains = chains[start_idx:end_idx]

    for chain in page_chains:
        status = "🟢" if chain.get('is_active', False) else "🔴"
        name = chain.get('name', 'Без названия')[:25]
        if len(chain.get('name', '')) > 25:
            name += "..."

        builder.button(
            text=f"{status} {name}",
            callback_data=ChainListCallback(
                action="view", chain_id=chain['id'])
        )

    # Пагинация
    if page > 0:
        builder.button(
            text="◀️ Назад",
            callback_data=ChainListCallback(
                action="view", chain_id=0, page=page - 1)
        )
    if end_idx < len(chains):
        builder.button(
            text="Вперёд ▶️",
            callback_data=ChainListCallback(
                action="view", chain_id=0, page=page + 1)
        )

    builder.button(
        text="🔙 В меню цепочек",
        callback_data=ChainMenuCallback(action="back")
    )

    # Adjust
    rows = [1] * len(page_chains)
    if page > 0 and end_idx < len(chains):
        rows.append(2)
    elif page > 0 or end_idx < len(chains):
        rows.append(1)
    rows.append(1)

    builder.adjust(*rows)
    return builder.as_markup()


def get_chain_view_keyboard(chain_id: int, is_active: bool, steps_count: int) -> InlineKeyboardMarkup:
    """Просмотр цепочки"""
    builder = InlineKeyboardBuilder()

    builder.button(
        text=f"📝 Шаги ({steps_count})",
        callback_data=ChainEditCallback(action="view_steps", chain_id=chain_id)
    )
    builder.button(
        text="➕ Добавить шаг",
        callback_data=ChainEditCallback(action="add_step", chain_id=chain_id)
    )

    if is_active:
        builder.button(
            text="⏸ Приостановить",
            callback_data=ChainListCallback(action="toggle", chain_id=chain_id)
        )
    else:
        builder.button(
            text="▶️ Активировать",
            callback_data=ChainListCallback(action="toggle", chain_id=chain_id)
        )

    if steps_count > 0:
        builder.button(
            text="🚀 Запустить для аудитории",
            callback_data=ChainEditCallback(
                action="start_send", chain_id=chain_id)
        )

    builder.button(
        text="🗑 Удалить цепочку",
        callback_data=ChainListCallback(action="delete", chain_id=chain_id)
    )
    builder.button(
        text="⬅️ К списку",
        callback_data=ChainListCallback(action="view", chain_id=0)
    )

    builder.adjust(2, 1, 1, 1, 1)
    return builder.as_markup()


def get_chain_steps_keyboard(chain_id: int, steps: list) -> InlineKeyboardMarkup:
    """Список шагов цепочки"""
    builder = InlineKeyboardBuilder()

    for step in steps:
        order = step.get('step_order', 0)
        content_preview = step.get('content', '')[:20].replace('\n', ' ')
        if len(step.get('content', '')) > 20:
            content_preview += "..."
        delay = step.get('delay_hours', 0)
        delay_str = f" (+{delay}ч)" if delay > 0 else ""

        builder.button(
            text=f"📌 Шаг {order}: {content_preview}{delay_str}",
            callback_data=ChainStepCallback(action="view", step_id=step['id'])
        )

    builder.button(
        text="➕ Добавить шаг",
        callback_data=ChainEditCallback(action="add_step", chain_id=chain_id)
    )
    builder.button(
        text="⬅️ К цепочке",
        callback_data=ChainListCallback(action="view", chain_id=chain_id)
    )

    # Adjust
    rows = [1] * len(steps) + [1, 1]
    builder.adjust(*rows)
    return builder.as_markup()


def get_chain_step_view_keyboard(step_id: int, chain_id: int, buttons: list) -> InlineKeyboardMarkup:
    """Просмотр шага цепочки"""
    builder = InlineKeyboardBuilder()

    # Показываем кнопки шага
    if buttons:
        builder.button(
            text=f"🔘 Кнопки ({len(buttons)})",
            callback_data=ChainStepCallback(
                action="view_buttons", step_id=step_id)
        )

    builder.button(
        text="✏️ Редактировать текст",
        callback_data=ChainStepCallback(action="edit", step_id=step_id)
    )
    builder.button(
        text="➕ Добавить кнопку",
        callback_data=ChainStepCallback(action="add_button", step_id=step_id)
    )
    builder.button(
        text="🗑 Удалить шаг",
        callback_data=ChainEditCallback(
            action="delete_step", chain_id=chain_id, step_id=step_id)
    )
    builder.button(
        text="⬅️ К шагам",
        callback_data=ChainEditCallback(action="view_steps", chain_id=chain_id)
    )

    builder.adjust(1)
    return builder.as_markup()


def get_chain_button_action_keyboard(step_id: int) -> InlineKeyboardMarkup:
    """Выбор действия для кнопки"""
    builder = InlineKeyboardBuilder()

    builder.button(
        text="➡️ Следующий шаг",
        callback_data=ChainButtonActionCallback(action_type="next_step")
    )
    builder.button(
        text="🔀 Перейти к шагу...",
        callback_data=ChainButtonActionCallback(action_type="goto_step")
    )
    builder.button(
        text="🔗 Ссылка (URL)",
        callback_data=ChainButtonActionCallback(action_type="url")
    )
    builder.button(
        text="⌨️ Команда бота",
        callback_data=ChainButtonActionCallback(action_type="command")
    )
    builder.button(
        text="⏹ Остановить цепочку",
        callback_data=ChainButtonActionCallback(action_type="stop_chain")
    )
    builder.button(
        text="💳 Оплата рациона",
        callback_data=ChainButtonActionCallback(action_type="payment_main")
    )
    builder.button(
        text="🥗 Оплата FMD",
        callback_data=ChainButtonActionCallback(action_type="payment_fmd")
    )
    builder.button(
        text="🎁 Оплата комплекта (скидка)",
        callback_data=ChainButtonActionCallback(action_type="payment_bundle")
    )
    builder.button(
        text="⬅️ Назад",
        callback_data=ChainStepCallback(action="view", step_id=step_id)
    )

    builder.adjust(1)
    return builder.as_markup()


def get_chain_step_buttons_keyboard(step_id: int, buttons: list) -> InlineKeyboardMarkup:
    """Список кнопок шага"""
    builder = InlineKeyboardBuilder()

    action_names = {
        'next_step': '➡️',
        'goto_step': '🔀',
        'url': '🔗',
        'command': '⌨️',
        'stop_chain': '⏹',
        'payment_main': '💳',
        'payment_fmd': '🥗',
        'payment_bundle': '🎁'
    }

    for btn in buttons:
        action_icon = action_names.get(btn.get('action_type', ''), '❓')
        text = btn.get('button_text', 'Кнопка')[:20]

        builder.button(
            text=f"{action_icon} {text}",
            callback_data=ChainStepCallback(
                action="edit_button", step_id=step_id, button_id=btn['id'])
        )

    builder.button(
        text="➕ Добавить кнопку",
        callback_data=ChainStepCallback(action="add_button", step_id=step_id)
    )
    builder.button(
        text="⬅️ К шагу",
        callback_data=ChainStepCallback(action="view", step_id=step_id)
    )

    rows = [1] * len(buttons) + [1, 1]
    builder.adjust(*rows)
    return builder.as_markup()


def get_chain_button_edit_keyboard(step_id: int, button_id: int) -> InlineKeyboardMarkup:
    """Редактирование кнопки шага"""
    builder = InlineKeyboardBuilder()

    builder.button(
        text="🗑 Удалить кнопку",
        callback_data=ChainStepCallback(
            action="delete_button", step_id=step_id, button_id=button_id)
    )
    builder.button(
        text="⬅️ К кнопкам",
        callback_data=ChainStepCallback(action="view_buttons", step_id=step_id)
    )

    builder.adjust(1)
    return builder.as_markup()


def get_chain_audience_keyboard(chain_id: int) -> InlineKeyboardMarkup:
    """Выбор аудитории для запуска цепочки"""
    builder = InlineKeyboardBuilder()

    builder.button(
        text="👥 Всем пользователям",
        callback_data=ChainAudienceCallback(audience="all")
    )
    builder.button(
        text="👆 Только /start (ничего не делали)",
        callback_data=ChainAudienceCallback(audience="start_only")
    )
    builder.button(
        text="💰 Оплатившие",
        callback_data=ChainAudienceCallback(audience="paid")
    )
    builder.button(
        text="❌ Не оплатившие",
        callback_data=ChainAudienceCallback(audience="not_paid")
    )
    builder.button(
        text="⬅️ Назад",
        callback_data=ChainListCallback(action="view", chain_id=chain_id)
    )

    builder.adjust(1)
    return builder.as_markup()


def get_chain_confirm_send_keyboard(chain_id: int) -> InlineKeyboardMarkup:
    """Подтверждение запуска цепочки для аудитории"""
    builder = InlineKeyboardBuilder()

    builder.button(
        text="✅ Запустить",
        callback_data=ChainEditCallback(
            action="confirm_send", chain_id=chain_id)
    )
    builder.button(
        text="❌ Отмена",
        callback_data=ChainListCallback(action="view", chain_id=chain_id)
    )

    builder.adjust(2)
    return builder.as_markup()


def get_chain_step_goto_keyboard(chain_id: int, steps: list, current_step_id: int) -> InlineKeyboardMarkup:
    """Выбор шага для перехода"""
    builder = InlineKeyboardBuilder()

    for step in steps:
        if step['id'] == current_step_id:
            continue  # Пропускаем текущий шаг
        order = step.get('step_order', 0)
        content_preview = step.get('content', '')[:15].replace('\n', ' ')
        if len(step.get('content', '')) > 15:
            content_preview += "..."

        builder.button(
            text=f"📌 Шаг {order}: {content_preview}",
            callback_data=ChainEditCallback(
                action="select_goto", chain_id=chain_id, step_id=step['id'])
        )

    builder.button(
        text="⬅️ Назад",
        callback_data=ChainStepCallback(
            action="add_button", step_id=current_step_id)
    )

    rows = [1] * (len(steps) - 1) + [1]
    builder.adjust(*rows)
    return builder.as_markup()


def build_chain_step_keyboard(buttons: list, chain_id: int, step_id: int) -> InlineKeyboardMarkup:
    """Построить клавиатуру для шага цепочки (для пользователя)"""
    builder = InlineKeyboardBuilder()

    for btn in buttons:
        action_type = btn.get('action_type', '')

        if action_type == 'url':
            # URL кнопка
            builder.button(
                text=btn.get('button_text', 'Ссылка'),
                url=btn.get('action_value', 'https://t.me')
            )
        else:
            # Callback кнопка
            builder.button(
                text=btn.get('button_text', 'Кнопка'),
                callback_data=ChainUserButtonCallback(
                    chain_id=chain_id,
                    step_id=step_id,
                    button_id=btn['id']
                )
            )

    builder.adjust(1)  # Каждая кнопка в отдельном ряду
    return builder.as_markup()


# ==================== User Management Keyboards ====================

def get_user_management_menu() -> InlineKeyboardMarkup:
    """Меню управления пользователями"""
    builder = InlineKeyboardBuilder()

    builder.button(
        text="👥 Все пользователи",
        callback_data=UserManageMenuCallback(action="list_all")
    )
    builder.button(
        text="💰 Оплатившие рационы",
        callback_data=UserListCallback(
            action="view", payment_filter="paid_main")
    )
    builder.button(
        text="🥗 Оплатившие FMD",
        callback_data=UserListCallback(
            action="view", payment_filter="paid_fmd")
    )
    builder.button(
        text="🎁 Оплатившие комплект",
        callback_data=UserListCallback(
            action="view", payment_filter="paid_bundle")
    )
    builder.button(
        text="🔥 Оплатившие Сушку",
        callback_data=UserListCallback(
            action="view", payment_filter="paid_dry")
    )
    builder.button(
        text="🔍 Поиск пользователя",
        callback_data=UserManageMenuCallback(action="search")
    )

    builder.adjust(1)
    return builder.as_markup()


def get_user_list_keyboard(users: list, page: int = 0, per_page: int = 10, filter_type: str = "all") -> InlineKeyboardMarkup:
    """Список пользователей с пагинацией"""
    builder = InlineKeyboardBuilder()

    start_idx = page * per_page
    end_idx = start_idx + per_page
    page_users = users[start_idx:end_idx]

    for user in page_users:
        # Формируем отображение пользователя
        username = user.get('username')
        first_name = user.get('first_name', 'Без имени')
        user_id = user.get('user_id')

        # Статус оплаты
        paid_main = user.get('has_paid', 0)
        paid_fmd = user.get('has_paid_fmd', 0)
        paid_bundle = user.get('has_paid_bundle', 0)
        paid_dry = user.get('has_paid_dry', 0)

        status_icons = []
        if paid_main:
            status_icons.append("💰")
        if paid_fmd:
            status_icons.append("🥗")
        if paid_bundle:
            status_icons.append("🎁")
        if paid_dry:
            status_icons.append("🔥")

        status_str = "".join(status_icons) if status_icons else "⚪"

        display_name = f"@{username}" if username else first_name
        display_name = display_name[:20] + \
            "..." if len(display_name) > 20 else display_name

        builder.button(
            text=f"{status_str} {display_name}",
            callback_data=UserActionCallback(action="view", user_id=user_id)
        )

    # Пагинация
    nav_buttons = []
    if page > 0:
        builder.button(
            text="◀️ Назад",
            callback_data=UserListCallback(
                action="page", page=page - 1, payment_filter=filter_type)
        )
        nav_buttons.append(1)
    if end_idx < len(users):
        builder.button(
            text="Вперёд ▶️",
            callback_data=UserListCallback(
                action="page", page=page + 1, payment_filter=filter_type)
        )
        nav_buttons.append(1)

    builder.button(
        text="🔙 В меню управления",
        callback_data=UserManageMenuCallback(action="back")
    )

    # Adjust: пользователи по одному, затем навигация
    rows = [1] * len(page_users)
    if page > 0 and end_idx < len(users):
        rows.append(2)  # Обе кнопки навигации
    elif page > 0 or end_idx < len(users):
        rows.append(1)  # Одна кнопка навигации
    rows.append(1)  # Кнопка "В меню"

    builder.adjust(*rows)
    return builder.as_markup()


def get_user_view_keyboard(user_id: int, has_paid: bool, has_paid_fmd: bool, has_paid_bundle: bool, has_paid_dry: bool = False) -> InlineKeyboardMarkup:
    """Просмотр и управление конкретным пользователем"""
    builder = InlineKeyboardBuilder()

    # Кнопки сброса оплаты (показываем только если оплачено)
    if has_paid:
        builder.button(
            text="❌ Сбросить оплату рациона",
            callback_data=UserActionCallback(
                action="reset_main", user_id=user_id)
        )

    if has_paid_fmd:
        builder.button(
            text="❌ Сбросить оплату FMD",
            callback_data=UserActionCallback(
                action="reset_fmd", user_id=user_id)
        )

    if has_paid_bundle:
        builder.button(
            text="❌ Сбросить оплату комплекта",
            callback_data=UserActionCallback(
                action="reset_bundle", user_id=user_id)
        )

    if has_paid_dry:
        builder.button(
            text="❌ Сбросить оплату Сушки",
            callback_data=UserActionCallback(
                action="reset_dry", user_id=user_id)
        )

    if has_paid or has_paid_fmd or has_paid_bundle or has_paid_dry:
        builder.button(
            text="🗑 Сбросить ВСЕ оплаты",
            callback_data=UserActionCallback(
                action="reset_all", user_id=user_id)
        )

    builder.button(
        text="⬅️ К списку",
        callback_data=UserManageMenuCallback(action="list_all")
    )

    builder.adjust(1)
    return builder.as_markup()


def get_user_confirm_reset_keyboard(user_id: int, reset_type: str) -> InlineKeyboardMarkup:
    """Подтверждение сброса оплаты"""
    builder = InlineKeyboardBuilder()

    builder.button(
        text="✅ Да, сбросить",
        callback_data=UserActionCallback(
            action=f"confirm_{reset_type}", user_id=user_id)
    )
    builder.button(
        text="❌ Отмена",
        callback_data=UserActionCallback(action="view", user_id=user_id)
    )

    builder.adjust(2)
    return builder.as_markup()


# ==================== Support (Отдел Заботы) ====================

def get_support_reply_keyboard(user_id: int, question_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для ответа модератора на вопрос пользователя"""
    builder = InlineKeyboardBuilder()

    builder.button(
        text="💬 Ответить",
        callback_data=SupportReplyCallback(
            action="reply", user_id=user_id, question_id=question_id)
    )

    return builder.as_markup()
