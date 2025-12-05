#!/usr/bin/env python3
import re
import os

FILES = {
    "1200cal.md": 1200,
    "1300-1400cal.md": 1300,
    "1300cal.md": 1300,
    "1500cal.md": 1500,
    "1600cal.md": 1600,
    "1700cal.md": 1700,
    "1800cal.md": 1800,
    "1900-2000cal.md": 1900,
    "2000-2100cal.md": 2100,
}


def parse_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    days = {}
    day_sections = re.split(r'\n---\n|\n--- \n', content)

    for section in day_sections:
        section = section.strip()
        if not section or 'ДЕНЬ' not in section:
            continue

        day_match = re.search(r'ДЕНЬ\s+(\d+)', section)
        if not day_match:
            continue

        day_num = int(day_match.group(1))

        # Парсим завтрак, обед, ужин
        breakfast = parse_meal(section, 'Завтрак', '🌅')
        lunch = parse_meal(section, 'Обед', '🍽')
        dinner = parse_meal(section, 'Ужин', '🌙')

        if breakfast and lunch and dinner:
            days[day_num] = {
                'breakfast': breakfast,
                'lunch': lunch,
                'dinner': dinner
            }

    return days


def parse_meal(text, meal_type, emoji):
    pattern = f'{meal_type}:([^\n]+)'
    match = re.search(pattern, text)
    if not match:
        return None

    title = match.group(1).strip()

    # Находим начало блока
    start = match.end()

    # Находим конец (следующий прием пищи или конец текста)
    next_meals = ['Завтрак:', 'Обед:', 'Ужин:']
    end = len(text)
    for nm in next_meals:
        pos = text.find(nm, start)
        if pos != -1 and pos < end:
            end = pos

    meal_text = text[start:end].strip()

    # Форматирование
    result = f'{emoji} <b>{meal_type} — {title}</b>\n\n'

    lines = meal_text.split('\n')
    in_ingredients = False
    in_preparation = False

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if line.startswith('КБЖУ'):
            line = re.sub(r'^КБЖУ[:\s]*', '<b>КБЖУ:</b> ', line)
            result += line + '\n'
        elif line.lower() == 'ингредиенты:':
            result += '\n<b>Ингредиенты:</b>\n'
            in_ingredients = True
            in_preparation = False
        elif line.lower() == 'приготовление:':
            result += '\n<b>Приготовление:</b>\n'
            in_preparation = True
            in_ingredients = False
        elif line.startswith('•') or line.startswith('-') or line.startswith('*'):
            result += '• ' + line[1:].strip() + '\n'
        elif re.match(r'^\d+\.', line):
            result += line + '\n'
        else:
            result += line + '\n'

    return result.strip()


def main():
    meal_dir = 'meal_days'
    all_recipes = {}

    for filename, calories in FILES.items():
        path = os.path.join(meal_dir, filename)
        if not os.path.exists(path):
            print(f'SKIP {filename}: file not found')
            continue

        print(f'Parsing {filename} -> {calories} kcal...')
        days = parse_file(path)

        if calories in all_recipes:
            print(f'  WARNING: {calories} kcal already exists, merging...')
            all_recipes[calories].update(days)
        else:
            all_recipes[calories] = days

        print(f'  Found {len(days)} days')

    # Генерация recipes.py
    print('\nGenerating recipes.py...')

    with open('meal_days/instructions.md', 'r', encoding='utf-8') as f:
        instructions = f.read().strip()

    output = '# База рецептов по калорийности\n'
    output += '# Структура: RECIPES[калории][день] = {"breakfast": ..., "lunch": ..., "dinner": ...}\n\n'
    output += f'INSTRUCTION = """{instructions}"""\n\n'
    output += 'RECIPES = {\n'

    for calories in sorted(all_recipes.keys()):
        output += f'    {calories}: {{\n'
        for day in sorted(all_recipes[calories].keys()):
            meals = all_recipes[calories][day]
            output += f'        {day}: {{\n'
            output += f'            "breakfast": """{meals["breakfast"]}""",\n\n'
            output += f'            "lunch": """{meals["lunch"]}""",\n\n'
            output += f'            "dinner": """{meals["dinner"]}"""\n'
            output += '        },\n'
        output += '    },\n'

    output += '}\n\n'

    # Добавляем функции из оригинального recipes.py
    output += '''
def get_recipe_from_db(calories: int, day: int, meal_type: str):
    """Получает кастомный рецепт из БД если есть"""
    from .database import load_custom_recipe
    return load_custom_recipe(calories, day, meal_type)

async def get_recipe_text_async(calories: int, day: int, meal_type: str) -> str:
    """Асинхронно получает текст рецепта (сначала из БД, потом из базы)"""
    custom = get_recipe_from_db(calories, day, meal_type)
    if custom:
        return custom
    
    if calories not in RECIPES or day not in RECIPES[calories]:
        return "Рецепт не найден"
    
    meal_text = RECIPES[calories][day].get(meal_type, "Рецепт не найден")
    return f"{INSTRUCTION}\\n\\n{meal_text}"

def get_recipe_text(calories: int, day: int, meal_type: str) -> str:
    """Синхронно получает текст рецепта"""
    custom = get_recipe_from_db(calories, day, meal_type)
    if custom:
        return custom
    
    if calories not in RECIPES or day not in RECIPES[calories]:
        return "Рецепт не найден"
    
    meal_text = RECIPES[calories][day].get(meal_type, "Рецепт не найден")
    return f"{INSTRUCTION}\\n\\n{meal_text}"

def get_available_calories() -> list:
    """Возвращает список доступных калорийностей"""
    return sorted(RECIPES.keys())

def get_days_count(calories: int) -> int:
    """Возвращает количество дней для заданной калорийности"""
    if calories not in RECIPES:
        return 0
    return len(RECIPES[calories])
'''

    with open('data/recipes_new.py', 'w', encoding='utf-8') as f:
        f.write(output)

    print(f'✓ Generated data/recipes_new.py')
    print(f'\nStats:')
    for calories in sorted(all_recipes.keys()):
        print(f'  {calories} kcal: {len(all_recipes[calories])} days')


if __name__ == '__main__':
    main()
