"""
Калькулятор калорий - пошаговая анкета для определения КБЖУ

Страницы:
1. Пол, Возраст, Рост, Вес
2. Шаги в день, Кардио (мин/нед), Силовые (мин/нед)
3. Цель, Гормональные нарушения
4. Уровень (любитель/проф)
5. Результаты

Формула: Mifflin-St Jeor + Activity Factor + Goal Adjustment
"""

import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import database as db
from keyboards.calculator_kb import (
    get_gender_keyboard,
    get_goal_keyboard,
    get_hormones_keyboard,
    get_level_keyboard,
    get_step2_nav_keyboard,
    get_results_keyboard,
    get_start_calculator_keyboard,
)
from keyboards.callbacks import (
    CalcGenderCallback,
    CalcGoalCallback,
    CalcHormonesCallback,
    CalcLevelCallback,
    CalcNavCallback,
    CalcStartCallback,
)
from keyboards.user_kb import get_main_menu, get_calories_keyboard

logger = logging.getLogger(__name__)
router = Router(name="calculator")


# ==================== FSM States ====================

class CalculatorState(StatesGroup):
    """Состояния калькулятора калорий"""
    # Страница 1
    waiting_gender = State()
    waiting_age = State()
    waiting_height = State()
    waiting_weight = State()

    # Страница 2
    waiting_steps = State()
    waiting_cardio = State()
    waiting_strength = State()

    # Страница 3
    waiting_goal = State()
    waiting_hormones = State()

    # Страница 4
    waiting_level = State()

    # Результаты
    showing_results = State()


# ==================== Calculation Functions ====================

def calculate_bmr(gender: str, weight: float, height: float, age: int) -> float:
    """
    Расчёт базового метаболизма по формуле Mifflin-St Jeor

    Мужчины: BMR = (10 × вес) + (6.25 × рост) - (5 × возраст) + 5
    Женщины: BMR = (10 × вес) + (6.25 × рост) - (5 × возраст) - 161
    """
    bmr = (10 * weight) + (6.25 * height) - (5 * age)
    if gender == "male":
        bmr += 5
    else:
        bmr -= 161
    return bmr


def calculate_activity_factor(steps: int, cardio_min: int, strength_min: int) -> float:
    """
    Расчёт коэффициента активности на основе:
    - Шагов в день
    - Кардио тренировок (мин/неделю)
    - Силовых тренировок (мин/неделю)

    Базовый коэффициент 1.2 (сидячий образ жизни)
    + бонус за шаги (до +0.15)
    + бонус за кардио (до +0.1)
    + бонус за силовые (до +0.15)
    """
    factor = 1.2  # Базовый (сидячий)

    # Шаги: каждые 2500 шагов добавляют ~0.05, макс +0.15 при 10000+
    if steps >= 10000:
        factor += 0.15
    elif steps >= 7500:
        factor += 0.12
    elif steps >= 5000:
        factor += 0.08
    elif steps >= 2500:
        factor += 0.04

    # Кардио: 30-60 мин 3 раза = 90-180 мин, добавляет до +0.1
    if cardio_min >= 180:
        factor += 0.1
    elif cardio_min >= 120:
        factor += 0.07
    elif cardio_min >= 60:
        factor += 0.05
    elif cardio_min >= 30:
        factor += 0.02

    # Силовые: 3х60 = 180 мин, добавляет до +0.15
    if strength_min >= 240:
        factor += 0.15
    elif strength_min >= 180:
        factor += 0.12
    elif strength_min >= 120:
        factor += 0.08
    elif strength_min >= 60:
        factor += 0.05

    return min(factor, 1.9)  # Максимум 1.9


def calculate_goal_adjustment(goal: str, maintenance: float) -> float:
    """
    Корректировка калорий в зависимости от цели

    - Похудение: -15-20% от поддержки
    - Поддержка: 0%
    - Набор массы: +10-15%
    """
    if goal == "loss":
        return maintenance * 0.82  # -18%
    elif goal == "gain":
        return maintenance * 1.12  # +12%
    return maintenance


def calculate_hormones_adjustment(hormones: str, calories: float) -> float:
    """
    Корректировка при гормональных нарушениях

    Гормональные проблемы могут замедлять метаболизм на 5-15%
    """
    if hormones == "none":
        return calories
    elif hormones == "hypothyroidism":
        return calories * 0.92  # -8%
    elif hormones == "insulin":
        return calories * 0.95  # -5%
    elif hormones == "deficiency":
        return calories * 0.95  # -5%
    else:  # other
        return calories * 0.93  # -7%


def calculate_effective_weight(gender: str, height: float) -> float:
    """
    Расчёт эффективного веса (оптимальный вес при ~10% жира для мужчин, ~15% для женщин)

    Формула на основе роста (упрощённая версия формулы Лоренца)
    """
    if gender == "male":
        # Мужчины: рост - 100 - (рост - 150) / 4
        return height - 100 - (height - 150) / 4
    else:
        # Женщины: рост - 100 - (рост - 150) / 2
        return height - 100 - (height - 150) / 2


def calculate_bmi(weight: float, height: float) -> float:
    """Расчёт ИМТ (Индекс массы тела)"""
    height_m = height / 100
    return weight / (height_m ** 2)


def get_bmi_interpretation(bmi: float) -> str:
    """Интерпретация ИМТ"""
    if bmi < 16:
        return "🔴 <b>16 и менее</b> — Выраженный дефицит массы тела"
    elif bmi < 18.5:
        return "🟠 <b>16—18.5</b> — Недостаточная (дефицит) масса тела"
    elif bmi < 25:
        return "🟢 <b>18.5—24.99</b> — Норма"
    elif bmi < 30:
        return "🟡 <b>25—30</b> — Избыточная масса тела (предожирение)"
    elif bmi < 35:
        return "🟠 <b>30—35</b> — Ожирение"
    elif bmi < 40:
        return "🔴 <b>35—40</b> — Ожирение резкое"
    else:
        return "🔴 <b>40 и более</b> — Очень резкое ожирение"


def calculate_macros(calories: float, weight: float, gender: str, goal: str, level: str) -> dict:
    """
    Расчёт БЖУ

    Белки: 1.6-2.2 г на кг веса (больше для набора и профи)
    Жиры: 0.8-1.2 г на кг веса
    Углеводы: остаток
    """
    # Коэффициент белка
    protein_multiplier = 1.8
    if goal == "gain" or level == "professional":
        protein_multiplier = 2.2
    elif goal == "loss":
        protein_multiplier = 2.0  # Больше белка при похудении для сохранения мышц

    # Коэффициент жиров
    fat_multiplier = 1.0
    if gender == "female":
        fat_multiplier = 1.1  # Женщинам нужно чуть больше жиров

    protein = weight * protein_multiplier
    fats = weight * fat_multiplier

    # Калории от белков и жиров
    protein_calories = protein * 4
    fat_calories = fats * 9

    # Углеводы - остаток
    carbs_calories = calories - protein_calories - fat_calories
    carbs = max(carbs_calories / 4, 50)  # Минимум 50г углеводов

    return {
        "protein": round(protein),
        "fats": round(fats),
        "carbs": round(carbs, 1)
    }


def find_closest_ration(calories: float) -> int:
    """Найти ближайший рацион по калорийности"""
    available = [1600, 1700, 1800, 1900, 2000, 2100]
    return min(available, key=lambda x: abs(x - calories))


# ==================== Message Texts ====================

def get_step1_text() -> str:
    """Текст для страницы 1"""
    return """📊 <b>Калькулятор калорий</b>
<i>Страница 1 из 5</i>

━━━━━━━━━━━━━━━━━━━━

<b>Пол</b>
Выберите ваш пол:"""


def get_age_text() -> str:
    """Текст для ввода возраста"""
    return """📊 <b>Калькулятор калорий</b>
<i>Страница 1 из 5</i>

━━━━━━━━━━━━━━━━━━━━

<b>Возраст</b>
Введите ваш возраст (число лет):"""


def get_height_text() -> str:
    """Текст для ввода роста"""
    return """📊 <b>Калькулятор калорий</b>
<i>Страница 1 из 5</i>

━━━━━━━━━━━━━━━━━━━━

<b>Рост</b>
Введите ваш рост в сантиметрах:"""


def get_weight_text() -> str:
    """Текст для ввода веса"""
    return """📊 <b>Калькулятор калорий</b>
<i>Страница 1 из 5</i>

━━━━━━━━━━━━━━━━━━━━

<b>Вес</b>
Введите ваш вес в килограммах:"""


def get_step2_text() -> str:
    """Текст для страницы 2"""
    return """📊 <b>Калькулятор калорий</b>
<i>Страница 2 из 5</i>

━━━━━━━━━━━━━━━━━━━━

<b>Количество шагов в день</b>
<i>Количество шагов можно посмотреть в приложении "Здоровье", которое предустановлено на вашем iPhone. Рекомендуется ввести среднее количество шагов за месяц. Если у вас Android и не предустановлен счётчик шагов, то введите примерное значение из расчёта, что если вы ходите 30 минут в день - это 5000 шагов, если 60, то 10000.
Минимальное рекомендуемое значение – 5000 шагов в сутки.</i>

Введите количество шагов:"""


def get_cardio_text() -> str:
    """Текст для ввода кардио"""
    return """📊 <b>Калькулятор калорий</b>
<i>Страница 2 из 5</i>

━━━━━━━━━━━━━━━━━━━━

<b>Кардио тренировки</b>
<i>Суммарное количество кардио тренировок в неделю, в минутах. Например, у вас 3 кардио тренировки в неделю по 20 минут каждая. Суммарное время будет 60 минут. Если не делаете, то поставьте 0. Если вы занимаетесь кроссфитом, то также укажите значение в этом поле.</i>

Введите минуты кардио в неделю:"""


def get_strength_text() -> str:
    """Текст для ввода силовых"""
    return """📊 <b>Калькулятор калорий</b>
<i>Страница 2 из 5</i>

━━━━━━━━━━━━━━━━━━━━

<b>Силовые тренировки</b>
<i>Суммарное количество силовых тренировок в неделю, в минутах. Например, у вас 3 силовых тренировки в неделю по 60 минут каждая. Суммарное время будет 180 минут. Если не делаете, то поставьте 0.</i>

Введите минуты силовых в неделю:"""


def get_step3_goal_text() -> str:
    """Текст для страницы 3 (цель)"""
    return """📊 <b>Калькулятор калорий</b>
<i>Страница 3 из 5</i>

━━━━━━━━━━━━━━━━━━━━

<b>Цель</b>
Выберите вашу цель:"""


def get_step3_hormones_text() -> str:
    """Текст для страницы 3 (гормоны)"""
    return """📊 <b>Калькулятор калорий</b>
<i>Страница 3 из 5</i>

━━━━━━━━━━━━━━━━━━━━

<b>Есть ли у вас гормональные нарушения?</b>

<i>Если не уверены, выберите первый вариант.</i>"""


def get_step4_text() -> str:
    """Текст для страницы 4"""
    return """📊 <b>Калькулятор калорий</b>
<i>Страница 4 из 5</i>

━━━━━━━━━━━━━━━━━━━━

<b>Ваш уровень</b>
Выберите ваш уровень:"""


def format_results(data: dict) -> str:
    """Форматирование результатов"""
    bmi = data['bmi']
    bmi_interpretation = get_bmi_interpretation(bmi)

    # Определяем, какая строка ИМТ актуальна для пользователя
    bmi_highlight = ""
    if bmi < 16:
        bmi_highlight = "🔴"
    elif bmi < 18.5:
        bmi_highlight = "🟠"
    elif bmi < 25:
        bmi_highlight = "🟢"
    elif bmi < 30:
        bmi_highlight = "🟡"
    elif bmi < 35:
        bmi_highlight = "🟠"
    else:
        bmi_highlight = "🔴"

    return f"""📊 <b>Результаты расчёта</b>
<i>Страница 5 из 5</i>

━━━━━━━━━━━━━━━━━━━━

<b>🔥 Ваша калорийность</b>
<i>Ваша дневная калорийность составит</i>
<code>{data['calories']}</code>

━━━━━━━━━━━━━━━━━━━━

<b>🥩 Белки</b>
<i>Рекомендуемое количество белка в граммах</i>
<code>{data['protein']}</code>

━━━━━━━━━━━━━━━━━━━━

<b>🧈 Жиры</b>
<i>Рекомендуемое количество жиров в граммах</i>
<code>{data['fats']}</code>

━━━━━━━━━━━━━━━━━━━━

<b>🍞 Углеводы</b>
<i>Рекомендуемое количество углеводов в граммах</i>
<code>{data['carbs']}</code>

━━━━━━━━━━━━━━━━━━━━

<b>⚖️ Эффективный вес</b>
<i>Эффективный вес — оптимальный вес для вашего роста при 10% жира для мужчин и 15% жира для женщин</i>
<code>{data['effective_weight']}</code>

━━━━━━━━━━━━━━━━━━━━

<b>📏 Индекс массы тела</b>
<i>ИМТ — величина, позволяющая оценить степень соответствия массы человека и его роста и тем самым косвенно оценить, является ли масса недостаточной, нормальной или избыточной. Данный параметр не подходит для оценки спортсменов ввиду развитой мускулатуры и как следствие высокого ИМТ.</i>
<code>{data['bmi']}</code>

<b>Интерпретация показателей:</b>
{"🔴" if bmi < 16 else "⚪️"} <b>16 и менее</b> — Выраженный дефицит массы тела
{"🟠" if 16 <= bmi < 18.5 else "⚪️"} <b>16—18.5</b> — Недостаточная (дефицит) масса тела
{"🟢" if 18.5 <= bmi < 25 else "⚪️"} <b>18,5—24.99</b> — Норма
{"🟡" if 25 <= bmi < 30 else "⚪️"} <b>25—30</b> — Избыточная масса тела (предожирение)
{"🟠" if 30 <= bmi < 35 else "⚪️"} <b>30—35</b> — Ожирение
{"🔴" if 35 <= bmi < 40 else "⚪️"} <b>35—40</b> — Ожирение резкое
{"🔴" if bmi >= 40 else "⚪️"} <b>40 и более</b> — Очень резкое ожирение

━━━━━━━━━━━━━━━━━━━━

💡 <b>Рекомендуемый рацион: {data['recommended_ration']} ккал</b>"""


# ==================== Handlers ====================

@router.callback_query(CalcStartCallback.filter())
async def start_calculator(callback: CallbackQuery, state: FSMContext):
    """Запуск калькулятора калорий"""
    await state.clear()
    await state.set_state(CalculatorState.waiting_gender)

    await callback.message.edit_text(
        get_step1_text(),
        reply_markup=get_gender_keyboard(),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@router.callback_query(CalcGenderCallback.filter())
async def process_gender(callback: CallbackQuery, callback_data: CalcGenderCallback, state: FSMContext):
    """Обработка выбора пола"""
    await state.update_data(gender=callback_data.gender)
    await state.set_state(CalculatorState.waiting_age)

    await callback.message.edit_text(
        get_age_text(),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@router.message(CalculatorState.waiting_age)
async def process_age(message: Message, state: FSMContext):
    """Обработка ввода возраста"""
    try:
        age = int(message.text.strip())
        if age < 10 or age > 120:
            await message.answer(
                "❌ Пожалуйста, введите корректный возраст (10-120 лет)."
            )
            return
    except ValueError:
        await message.answer(
            "❌ Пожалуйста, введите число (ваш возраст в годах)."
        )
        return

    await state.update_data(age=age)
    await state.set_state(CalculatorState.waiting_height)

    await message.answer(
        get_height_text(),
        parse_mode=ParseMode.HTML
    )


@router.message(CalculatorState.waiting_height)
async def process_height(message: Message, state: FSMContext):
    """Обработка ввода роста"""
    try:
        height = float(message.text.strip().replace(',', '.'))
        if height < 100 or height > 250:
            await message.answer(
                "❌ Пожалуйста, введите корректный рост (100-250 см)."
            )
            return
    except ValueError:
        await message.answer(
            "❌ Пожалуйста, введите число (ваш рост в сантиметрах)."
        )
        return

    await state.update_data(height=height)
    await state.set_state(CalculatorState.waiting_weight)

    await message.answer(
        get_weight_text(),
        parse_mode=ParseMode.HTML
    )


@router.message(CalculatorState.waiting_weight)
async def process_weight(message: Message, state: FSMContext):
    """Обработка ввода веса"""
    try:
        weight = float(message.text.strip().replace(',', '.'))
        if weight < 30 or weight > 300:
            await message.answer(
                "❌ Пожалуйста, введите корректный вес (30-300 кг)."
            )
            return
    except ValueError:
        await message.answer(
            "❌ Пожалуйста, введите число (ваш вес в килограммах)."
        )
        return

    await state.update_data(weight=weight)
    await state.set_state(CalculatorState.waiting_steps)

    await message.answer(
        get_step2_text(),
        parse_mode=ParseMode.HTML
    )


@router.message(CalculatorState.waiting_steps)
async def process_steps(message: Message, state: FSMContext):
    """Обработка ввода шагов"""
    try:
        steps = int(message.text.strip())
        if steps < 0 or steps > 100000:
            await message.answer(
                "❌ Пожалуйста, введите корректное количество шагов (0-100000)."
            )
            return
    except ValueError:
        await message.answer(
            "❌ Пожалуйста, введите число (количество шагов в день)."
        )
        return

    await state.update_data(steps=steps)
    await state.set_state(CalculatorState.waiting_cardio)

    await message.answer(
        get_cardio_text(),
        parse_mode=ParseMode.HTML
    )


@router.message(CalculatorState.waiting_cardio)
async def process_cardio(message: Message, state: FSMContext):
    """Обработка ввода кардио"""
    try:
        cardio = int(message.text.strip())
        if cardio < 0 or cardio > 2000:
            await message.answer(
                "❌ Пожалуйста, введите корректное количество минут (0-2000)."
            )
            return
    except ValueError:
        await message.answer(
            "❌ Пожалуйста, введите число (минуты кардио в неделю)."
        )
        return

    await state.update_data(cardio=cardio)
    await state.set_state(CalculatorState.waiting_strength)

    await message.answer(
        get_strength_text(),
        parse_mode=ParseMode.HTML
    )


@router.message(CalculatorState.waiting_strength)
async def process_strength(message: Message, state: FSMContext):
    """Обработка ввода силовых тренировок"""
    try:
        strength = int(message.text.strip())
        if strength < 0 or strength > 2000:
            await message.answer(
                "❌ Пожалуйста, введите корректное количество минут (0-2000)."
            )
            return
    except ValueError:
        await message.answer(
            "❌ Пожалуйста, введите число (минуты силовых в неделю)."
        )
        return

    await state.update_data(strength=strength)
    await state.set_state(CalculatorState.waiting_goal)

    await message.answer(
        get_step3_goal_text(),
        reply_markup=get_goal_keyboard(),
        parse_mode=ParseMode.HTML
    )


@router.callback_query(CalcGoalCallback.filter())
async def process_goal(callback: CallbackQuery, callback_data: CalcGoalCallback, state: FSMContext):
    """Обработка выбора цели"""
    await state.update_data(goal=callback_data.goal)
    await state.set_state(CalculatorState.waiting_hormones)

    await callback.message.edit_text(
        get_step3_hormones_text(),
        reply_markup=get_hormones_keyboard(),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@router.callback_query(CalcHormonesCallback.filter())
async def process_hormones(callback: CallbackQuery, callback_data: CalcHormonesCallback, state: FSMContext):
    """Обработка выбора гормональных нарушений"""
    await state.update_data(hormones=callback_data.hormones)
    await state.set_state(CalculatorState.waiting_level)

    await callback.message.edit_text(
        get_step4_text(),
        reply_markup=get_level_keyboard(),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@router.callback_query(CalcLevelCallback.filter())
async def process_level(callback: CallbackQuery, callback_data: CalcLevelCallback, state: FSMContext):
    """Обработка выбора уровня и показ результатов"""
    await state.update_data(level=callback_data.level)

    # Получаем все данные
    data = await state.get_data()

    # Расчёты
    gender = data['gender']
    age = data['age']
    height = data['height']
    weight = data['weight']
    steps = data['steps']
    cardio = data['cardio']
    strength = data['strength']
    goal = data['goal']
    hormones = data['hormones']
    level = callback_data.level

    # BMR
    bmr = calculate_bmr(gender, weight, height, age)

    # Activity Factor
    activity_factor = calculate_activity_factor(steps, cardio, strength)

    # Maintenance calories
    maintenance = bmr * activity_factor

    # Goal adjustment
    goal_adjusted = calculate_goal_adjustment(goal, maintenance)

    # Hormones adjustment
    final_calories = calculate_hormones_adjustment(hormones, goal_adjusted)

    # Macros
    macros = calculate_macros(final_calories, weight, gender, goal, level)

    # Effective weight and BMI
    effective_weight = calculate_effective_weight(gender, height)
    bmi = calculate_bmi(weight, height)

    # Recommended ration
    recommended_ration = find_closest_ration(final_calories)

    # Prepare results
    results = {
        'calories': round(final_calories, 1),
        'protein': macros['protein'],
        'fats': macros['fats'],
        'carbs': macros['carbs'],
        'effective_weight': round(effective_weight),
        'bmi': round(bmi, 1),
        'recommended_ration': recommended_ration
    }

    # Save to state for potential restart
    await state.update_data(results=results)
    await state.set_state(CalculatorState.showing_results)

    # Save to database
    await db.save_calculator_result(
        user_id=callback.from_user.id,
        gender=gender,
        age=age,
        height=height,
        weight=weight,
        steps=steps,
        cardio=cardio,
        strength=strength,
        goal=goal,
        hormones=hormones,
        level=level,
        calories=results['calories'],
        protein=results['protein'],
        fats=results['fats'],
        carbs=results['carbs']
    )

    await callback.message.edit_text(
        format_results(results),
        reply_markup=get_results_keyboard(),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


# ==================== Navigation ====================

@router.callback_query(CalcNavCallback.filter(F.action == "back_to_step2"))
async def nav_back_to_step2(callback: CallbackQuery, state: FSMContext):
    """Назад к странице 2"""
    await state.set_state(CalculatorState.waiting_steps)
    await callback.message.edit_text(
        get_step2_text(),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@router.callback_query(CalcNavCallback.filter(F.action == "back_to_step3"))
async def nav_back_to_step3(callback: CallbackQuery, state: FSMContext):
    """Назад к странице 3"""
    await state.set_state(CalculatorState.waiting_goal)
    await callback.message.edit_text(
        get_step3_goal_text(),
        reply_markup=get_goal_keyboard(),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@router.callback_query(CalcNavCallback.filter(F.action == "restart"))
async def nav_restart(callback: CallbackQuery, state: FSMContext):
    """Перезапуск калькулятора"""
    await state.clear()
    await state.set_state(CalculatorState.waiting_gender)

    await callback.message.edit_text(
        get_step1_text(),
        reply_markup=get_gender_keyboard(),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@router.callback_query(CalcNavCallback.filter(F.action == "to_rations"))
async def nav_to_rations(callback: CallbackQuery, state: FSMContext):
    """Переход к выбору рациона"""
    await state.clear()

    await callback.message.edit_text(
        "🔥 <b>Выбери калорийность рациона:</b>\n\n"
        "Доступные варианты от 1200 до 2100 ккал.",
        reply_markup=get_calories_keyboard(),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()
